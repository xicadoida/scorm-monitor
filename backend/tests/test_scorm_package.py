import asyncio
from io import BytesIO
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scorm_package import (  # noqa: E402
    ScormPackageError,
    ScormPackageLimits,
    _validate_member,
    save_upload_to_path,
    validate_and_extract_scorm,
)


class ChunkedUpload:
    """Pequena implementação assíncrona compatível com UploadFile.read."""

    def __init__(self, content: bytes, chunk_size: int = 17):
        self.content = content
        self.chunk_size = chunk_size
        self.position = 0

    async def read(self, size: int = -1) -> bytes:
        if self.position >= len(self.content):
            return b""
        requested = self.chunk_size if size < 0 else min(size, self.chunk_size)
        chunk = self.content[self.position : self.position + requested]
        self.position += len(chunk)
        return chunk


class InvalidUpload:
    async def read(self, _size: int = -1):
        return "not-bytes"


def write_zip(path: Path, entries, compression: int = zipfile.ZIP_DEFLATED) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for entry in entries:
            if len(entry) == 2:
                name, content = entry
                archive.writestr(name, content)
            else:
                info, content, _ = entry
                archive.writestr(info, content)


def valid_entries(prefix: str = ""):
    root = f"{prefix.rstrip('/')}/" if prefix else ""
    return [
        (f"{root}imsmanifest.xml", "<manifest identifier='curso' />"),
        (f"{root}scormdriver/indexAPI.html", "<html>SCORM launcher</html>"),
    ]


class ScormPackageValidationTests(unittest.TestCase):
    def validate_entries(self, entries, limits=None, compression=zipfile.ZIP_DEFLATED):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        archive_path = root / "package.zip"
        extraction_dir = root / "extracted"
        write_zip(archive_path, entries, compression)
        package = validate_and_extract_scorm(archive_path, extraction_dir, limits)
        return package, extraction_dir

    def assert_validation_error(self, entries, expected_code, limits=None, compression=zipfile.ZIP_DEFLATED):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "package.zip"
            extraction_dir = root / "extracted"
            write_zip(archive_path, entries, compression)

            with self.assertRaises(ScormPackageError) as raised:
                validate_and_extract_scorm(archive_path, extraction_dir, limits)

            self.assertEqual(expected_code, raised.exception.code)
            self.assertFalse(extraction_dir.exists())

    def test_accepts_valid_scorm_at_zip_root(self):
        package, extraction_dir = self.validate_entries(valid_entries())

        self.assertEqual(package.root_dir, extraction_dir)
        self.assertTrue(package.manifest_path.is_file())
        self.assertTrue(package.launcher_path.is_file())
        self.assertEqual(2, package.entry_count)

    def test_accepts_valid_scorm_inside_wrapper_directory(self):
        package, extraction_dir = self.validate_entries(valid_entries("curso-exportado"))

        self.assertEqual(package.root_dir, extraction_dir / "curso-exportado")
        self.assertEqual(
            package.root_dir / "scormdriver" / "indexAPI.html",
            package.launcher_path,
        )

    def test_reads_configurable_limits_from_environment(self):
        with patch.dict(
            "os.environ",
            {
                "SCORM_MAX_UPLOAD_BYTES": "123",
                "SCORM_MAX_ENTRIES": "45",
                "SCORM_MAX_UNCOMPRESSED_BYTES": "678",
                "SCORM_MAX_FILE_BYTES": "90",
                "SCORM_MAX_COMPRESSION_RATIO": "12.5",
            },
            clear=False,
        ):
            limits = ScormPackageLimits.from_environment()

        self.assertEqual(123, limits.max_upload_bytes)
        self.assertEqual(45, limits.max_entries)
        self.assertEqual(678, limits.max_uncompressed_bytes)
        self.assertEqual(90, limits.max_file_bytes)
        self.assertEqual(12.5, limits.max_compression_ratio)

    def test_rejects_missing_manifest(self):
        self.assert_validation_error(
            [("scormdriver/indexAPI.html", "<html>launcher</html>")],
            "manifest_missing",
        )

    def test_rejects_duplicate_manifests(self):
        self.assert_validation_error(
            valid_entries()
            + [
                ("outro-pacote/imsmanifest.xml", "<manifest />"),
                ("outro-pacote/scormdriver/indexAPI.html", "<html />"),
            ],
            "manifest_duplicated",
        )

    def test_rejects_missing_launcher(self):
        self.assert_validation_error(
            [("imsmanifest.xml", "<manifest />")],
            "launcher_missing",
        )

    def test_rejects_corrupted_zip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "corrupted.zip"
            extraction_dir = root / "extracted"
            archive_path.write_bytes(b"not a ZIP file")

            with self.assertRaises(ScormPackageError) as raised:
                validate_and_extract_scorm(archive_path, extraction_dir)

            self.assertEqual("invalid_zip", raised.exception.code)
            self.assertFalse(extraction_dir.exists())

    def test_rejects_unsafe_paths(self):
        for unsafe_path in (
            "../escape.txt",
            "/absolute.txt",
            "C:/windows-path.txt",
            "folder/../escape.txt",
        ):
            with self.subTest(unsafe_path=unsafe_path):
                self.assert_validation_error(
                    valid_entries() + [(unsafe_path, "unsafe")],
                    "unsafe_path",
                )

    def test_rejects_backslash_path(self):
        # ZipInfo normaliza barras invertidas no Windows ao ler um arquivo ZIP.
        # O teste injeta a entrada já decodificada para verificar a regra que
        # será aplicada no ambiente Linux de produção.
        entry = zipfile.ZipInfo("safe-name.txt")
        entry.filename = "folder\\backslash.txt"

        with self.assertRaises(ScormPackageError) as raised:
            _validate_member(entry)

        self.assertEqual("unsafe_path", raised.exception.code)

    def test_rejects_too_many_entries(self):
        limits = ScormPackageLimits(max_entries=2)
        self.assert_validation_error(
            valid_entries() + [("assets/extra.txt", "x")],
            "too_many_entries",
            limits,
        )

    def test_rejects_archive_above_compressed_limit(self):
        limits = ScormPackageLimits(max_upload_bytes=60)
        self.assert_validation_error(
            valid_entries() + [("assets/data.txt", "x" * 200)],
            "upload_too_large",
            limits,
        )

    def test_rejects_content_above_uncompressed_limit(self):
        limits = ScormPackageLimits(max_uncompressed_bytes=40)
        self.assert_validation_error(
            valid_entries() + [("assets/data.txt", "x" * 80)],
            "uncompressed_too_large",
            limits,
        )

    def test_rejects_file_above_individual_limit(self):
        limits = ScormPackageLimits(max_file_bytes=10)
        self.assert_validation_error(
            valid_entries(),
            "file_too_large",
            limits,
        )

    def test_rejects_excessive_compression_ratio(self):
        limits = ScormPackageLimits(max_compression_ratio=2)
        self.assert_validation_error(
            valid_entries() + [("assets/repeated.txt", "A" * 20_000)],
            "compression_ratio_too_large",
            limits,
        )

    def test_rejects_conflicting_entry_names(self):
        self.assert_validation_error(
            valid_entries()
            + [
                ("assets/Aula.html", "primeiro"),
                ("assets/aula.html", "segundo"),
            ],
            "conflicting_entries",
        )

    def test_rejects_file_directory_conflict(self):
        self.assert_validation_error(
            valid_entries()
            + [
                ("assets", "arquivo"),
                ("assets/aula.html", "conteúdo"),
            ],
            "file_directory_conflict",
        )

    def test_rejects_symbolic_link_entry(self):
        link = zipfile.ZipInfo("assets/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.assert_validation_error(
            valid_entries() + [(link, "target", None)],
            "unsupported_entry",
        )

    def test_rejects_malformed_directory_entry(self):
        malformed_directory = zipfile.ZipInfo("assets/not-a-directory/")
        malformed_directory.create_system = 3
        malformed_directory.external_attr = (stat.S_IFREG | 0o644) << 16
        self.assert_validation_error(
            valid_entries() + [(malformed_directory, b"", None)],
            "invalid_directory",
        )

    def test_rejects_unsupported_compression_method(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "package.zip"
            extraction_dir = root / "extracted"
            write_zip(archive_path, valid_entries())
            unsupported = zipfile.ZipInfo("unknown.bin")
            unsupported.compress_type = 99
            unsupported.file_size = 1
            unsupported.compress_size = 1

            with patch(
                "scorm_package.zipfile.ZipFile.infolist",
                return_value=[unsupported],
            ):
                with self.assertRaises(ScormPackageError) as raised:
                    validate_and_extract_scorm(archive_path, extraction_dir)

            self.assertEqual("unsupported_compression", raised.exception.code)
            self.assertFalse(extraction_dir.exists())

    def test_removes_extraction_directory_when_extraction_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "package.zip"
            extraction_dir = root / "extracted"
            write_zip(archive_path, valid_entries())

            with patch(
                "scorm_package.zipfile.ZipFile.open",
                side_effect=OSError("simulated extraction failure"),
            ):
                with self.assertRaises(ScormPackageError) as raised:
                    validate_and_extract_scorm(archive_path, extraction_dir)

            self.assertEqual("extraction_failed", raised.exception.code)
            self.assertFalse(extraction_dir.exists())


class ScormUploadPersistenceTests(unittest.TestCase):
    def test_saves_upload_in_chunks(self):
        content = BytesIO()
        with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in valid_entries():
                archive.writestr(name, value)

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "source.zip"
            size = asyncio.run(save_upload_to_path(ChunkedUpload(content.getvalue()), target))

            self.assertEqual(len(content.getvalue()), size)
            self.assertEqual(content.getvalue(), target.read_bytes())

    def test_rejects_streamed_upload_above_limit_and_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "source.zip"
            limits = ScormPackageLimits(max_upload_bytes=10)

            with self.assertRaises(ScormPackageError) as raised:
                asyncio.run(
                    save_upload_to_path(ChunkedUpload(b"0123456789A"), target, limits)
                )

            self.assertEqual("upload_too_large", raised.exception.code)
            self.assertFalse(target.exists())

    def test_does_not_remove_preexisting_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "source.zip"
            target.write_bytes(b"keep-this-file")

            with self.assertRaises(ScormPackageError) as raised:
                asyncio.run(save_upload_to_path(ChunkedUpload(b"new-content"), target))

            self.assertEqual("upload_write_failed", raised.exception.code)
            self.assertEqual(b"keep-this-file", target.read_bytes())

    def test_rejects_non_bytes_from_upload_and_removes_new_partial_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "source.zip"

            with self.assertRaises(ScormPackageError) as raised:
                asyncio.run(save_upload_to_path(InvalidUpload(), target))

            self.assertEqual("upload_read_failed", raised.exception.code)
            self.assertFalse(target.exists())
