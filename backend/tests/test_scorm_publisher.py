from pathlib import Path
import ftplib
import sys
import tempfile
import unittest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scorm_publisher import (  # noqa: E402
    ScormPublishError,
    finalize_replacement,
    publish_new_package,
    replace_published_package,
    rollback_new_package,
    rollback_replacement,
    validate_course_code_component,
)


class FakeFtpServer:
    """Servidor FTP em memória para testar staging e rollback sem rede."""

    base_dir = "/public_html/scorm"

    def __init__(self):
        self.directories = {self.base_dir}
        self.files = {}
        self.fail_upload = False
        self.fail_rename_calls = set()
        self.rename_count = 0

    def client(self):
        return FakeFtpClient(self)

    def add_package(self, course_code, files):
        package_dir = f"{self.base_dir}/{course_code}"
        self.directories.add(package_dir)
        for relative_name, content in files.items():
            parent = package_dir
            for part in relative_name.split("/")[:-1]:
                parent = f"{parent}/{part}"
                self.directories.add(parent)
            self.files[f"{package_dir}/{relative_name}"] = content
        return package_dir

    def package_directories(self, course_code):
        prefix = f"{self.base_dir}/{course_code}"
        return {directory for directory in self.directories if directory.startswith(prefix)}


class FakeFtpClient:
    def __init__(self, server):
        self.server = server

    def connect(self, _host, _port, timeout=None):
        del timeout

    def login(self, _user, _password):
        return "ok"

    def quit(self):
        return "bye"

    def mkd(self, remote_dir):
        if remote_dir in self.server.directories:
            raise ftplib.error_perm("550 directory exists")
        parent = remote_dir.rsplit("/", 1)[0]
        if parent not in self.server.directories:
            raise ftplib.error_perm("550 parent missing")
        self.server.directories.add(remote_dir)

    def storbinary(self, command, stream):
        if self.server.fail_upload:
            raise OSError("simulated upload failure")
        if not command.startswith("STOR "):
            raise AssertionError(f"Unexpected FTP command: {command}")
        remote_path = command[5:]
        parent = remote_path.rsplit("/", 1)[0]
        if parent not in self.server.directories:
            raise ftplib.error_perm("550 parent missing")
        self.server.files[remote_path] = stream.read()

    def nlst(self, remote_dir):
        if remote_dir not in self.server.directories:
            raise ftplib.error_perm("550 directory missing")
        prefix = f"{remote_dir.rstrip('/')}/"
        children = set()
        for directory in self.server.directories:
            if directory.startswith(prefix):
                remainder = directory[len(prefix) :]
                if remainder:
                    children.add(f"{prefix}{remainder.split('/', 1)[0]}")
        for file_path in self.server.files:
            if file_path.startswith(prefix):
                remainder = file_path[len(prefix) :]
                if remainder:
                    children.add(f"{prefix}{remainder.split('/', 1)[0]}")
        return sorted(children)

    def delete(self, remote_path):
        if remote_path not in self.server.files:
            raise ftplib.error_perm("550 file missing")
        del self.server.files[remote_path]

    def rmd(self, remote_dir):
        if remote_dir not in self.server.directories:
            raise ftplib.error_perm("550 directory missing")
        prefix = f"{remote_dir.rstrip('/')}/"
        if any(path.startswith(prefix) for path in self.server.files) or any(
            directory != remote_dir and directory.startswith(prefix)
            for directory in self.server.directories
        ):
            raise ftplib.error_perm("550 directory not empty")
        self.server.directories.remove(remote_dir)

    def rename(self, source, destination):
        self.server.rename_count += 1
        if self.server.rename_count in self.server.fail_rename_calls:
            raise ftplib.error_perm("550 simulated rename failure")
        if source not in self.server.directories:
            raise ftplib.error_perm("550 source missing")
        if destination in self.server.directories or destination in self.server.files:
            raise ftplib.error_perm("550 destination exists")

        source_prefix = f"{source.rstrip('/')}/"
        renamed_directories = set()
        for directory in self.server.directories:
            if directory == source:
                renamed_directories.add(destination)
            elif directory.startswith(source_prefix):
                renamed_directories.add(f"{destination}{directory[len(source):]}")
            else:
                renamed_directories.add(directory)
        self.server.directories = renamed_directories

        renamed_files = {}
        for file_path, content in self.server.files.items():
            if file_path.startswith(source_prefix):
                renamed_files[f"{destination}{file_path[len(source):]}"] = content
            else:
                renamed_files[file_path] = content
        self.server.files = renamed_files


def create_local_package(directory: Path) -> Path:
    (directory / "scormdriver").mkdir(parents=True)
    (directory / "imsmanifest.xml").write_text("<manifest />", encoding="utf-8")
    (directory / "scormdriver" / "indexAPI.html").write_text(
        "<html>launcher</html>", encoding="utf-8"
    )
    (directory / "assets").mkdir()
    (directory / "assets" / "new.txt").write_text("new package", encoding="utf-8")
    return directory


class ScormPublisherTests(unittest.TestCase):
    def call_publish_new(self, local_dir, server, course_code="curso-novo"):
        return publish_new_package(
            local_dir,
            course_code=course_code,
            ftp_host="fake-host",
            ftp_user="fake-user",
            ftp_password="fake-password",
            ftp_base_dir=server.base_dir,
            ftp_factory=server.client,
        )

    def call_replace(self, local_dir, server, course_code="curso"):
        return replace_published_package(
            local_dir,
            course_code=course_code,
            ftp_host="fake-host",
            ftp_user="fake-user",
            ftp_password="fake-password",
            ftp_base_dir=server.base_dir,
            ftp_factory=server.client,
        )

    def test_upload_failure_for_new_package_does_not_touch_existing_package(self):
        server = FakeFtpServer()
        old_dir = server.add_package("curso-antigo", {"old.txt": b"old package"})
        server.fail_upload = True

        with tempfile.TemporaryDirectory() as temporary:
            local_dir = create_local_package(Path(temporary))
            with self.assertRaises(ScormPublishError) as raised:
                self.call_publish_new(local_dir, server)

        self.assertEqual("publish_failed", raised.exception.code)
        self.assertEqual(b"old package", server.files[f"{old_dir}/old.txt"])
        self.assertFalse(
            any(".curso-novo.staging-" in directory for directory in server.directories)
        )

    def test_replace_upload_failure_keeps_current_package_available(self):
        server = FakeFtpServer()
        final_dir = server.add_package("curso", {"old.txt": b"old package"})
        server.fail_upload = True

        with tempfile.TemporaryDirectory() as temporary:
            local_dir = create_local_package(Path(temporary))
            with self.assertRaises(ScormPublishError) as raised:
                self.call_replace(local_dir, server)

        self.assertEqual("publish_failed", raised.exception.code)
        self.assertEqual(b"old package", server.files[f"{final_dir}/old.txt"])
        self.assertFalse(any(".curso.backup-" in directory for directory in server.directories))
        self.assertFalse(any(".curso.staging-" in directory for directory in server.directories))

    def test_swap_failure_restores_current_package(self):
        server = FakeFtpServer()
        final_dir = server.add_package("curso", {"old.txt": b"old package"})
        server.fail_rename_calls = {2}

        with tempfile.TemporaryDirectory() as temporary:
            local_dir = create_local_package(Path(temporary))
            with self.assertRaises(ScormPublishError) as raised:
                self.call_replace(local_dir, server)

        self.assertEqual("publish_swap_failed", raised.exception.code)
        self.assertEqual(b"old package", server.files[f"{final_dir}/old.txt"])
        self.assertFalse(any(".curso.backup-" in directory for directory in server.directories))
        self.assertFalse(any(".curso.staging-" in directory for directory in server.directories))

    def test_reports_when_backup_cannot_be_restored(self):
        server = FakeFtpServer()
        server.add_package("curso", {"old.txt": b"old package"})
        server.fail_rename_calls = {2, 3}

        with tempfile.TemporaryDirectory() as temporary:
            local_dir = create_local_package(Path(temporary))
            with self.assertRaises(ScormPublishError) as raised:
                self.call_replace(local_dir, server)

        self.assertEqual("backup_restore_failed", raised.exception.code)
        self.assertTrue(any(".curso.backup-" in directory for directory in server.directories))

    def test_successful_replacement_keeps_backup_until_finalized(self):
        server = FakeFtpServer()
        final_dir = server.add_package("curso", {"old.txt": b"old package"})

        with tempfile.TemporaryDirectory() as temporary:
            local_dir = create_local_package(Path(temporary))
            replacement = self.call_replace(local_dir, server)

        self.assertIn(f"{final_dir}/assets/new.txt", server.files)
        self.assertIn(f"{replacement.backup_dir}/old.txt", server.files)

        finalize_replacement(
            replacement,
            ftp_host="fake-host",
            ftp_user="fake-user",
            ftp_password="fake-password",
            ftp_factory=server.client,
        )

        self.assertIn(f"{final_dir}/assets/new.txt", server.files)
        self.assertNotIn(replacement.backup_dir, server.directories)
        self.assertNotIn(f"{replacement.backup_dir}/old.txt", server.files)

    def test_rollback_replacement_restores_previous_package(self):
        server = FakeFtpServer()
        final_dir = server.add_package("curso", {"old.txt": b"old package"})

        with tempfile.TemporaryDirectory() as temporary:
            replacement = self.call_replace(create_local_package(Path(temporary)), server)

        rollback_replacement(
            replacement,
            ftp_host="fake-host",
            ftp_user="fake-user",
            ftp_password="fake-password",
            ftp_factory=server.client,
        )

        self.assertEqual(b"old package", server.files[f"{final_dir}/old.txt"])
        self.assertNotIn(f"{final_dir}/assets/new.txt", server.files)

    def test_rollback_swap_failure_keeps_new_package_available(self):
        server = FakeFtpServer()
        final_dir = server.add_package("curso", {"old.txt": b"old package"})

        with tempfile.TemporaryDirectory() as temporary:
            replacement = self.call_replace(create_local_package(Path(temporary)), server)

        # As duas primeiras renomeações pertencem à substituição. A falha na
        # quarta ocorre ao tentar mover o backup antigo de volta ao caminho final.
        server.fail_rename_calls = {4}
        with self.assertRaises(ScormPublishError) as raised:
            rollback_replacement(
                replacement,
                ftp_host="fake-host",
                ftp_user="fake-user",
                ftp_password="fake-password",
                ftp_factory=server.client,
            )

        self.assertEqual("replacement_rollback_swap_failed", raised.exception.code)
        self.assertIn(f"{final_dir}/assets/new.txt", server.files)
        self.assertIn(f"{replacement.backup_dir}/old.txt", server.files)
        self.assertFalse(any(".rollback-" in directory for directory in server.directories))

    def test_replacement_recovers_course_with_missing_remote_package(self):
        server = FakeFtpServer()
        final_dir = f"{server.base_dir}/curso"

        with tempfile.TemporaryDirectory() as temporary:
            replacement = self.call_replace(create_local_package(Path(temporary)), server)

        self.assertIsNone(replacement.backup_dir)
        self.assertIn(f"{final_dir}/assets/new.txt", server.files)

        finalize_replacement(
            replacement,
            ftp_host="fake-host",
            ftp_user="fake-user",
            ftp_password="fake-password",
            ftp_factory=server.client,
        )
        self.assertIn(f"{final_dir}/assets/new.txt", server.files)

        rollback_replacement(
            replacement,
            ftp_host="fake-host",
            ftp_user="fake-user",
            ftp_password="fake-password",
            ftp_factory=server.client,
        )
        self.assertNotIn(final_dir, server.directories)

    def test_rollback_new_package_removes_only_the_new_publication(self):
        server = FakeFtpServer()
        old_dir = server.add_package("curso-antigo", {"old.txt": b"old package"})

        with tempfile.TemporaryDirectory() as temporary:
            final_dir = self.call_publish_new(create_local_package(Path(temporary)), server)

        rollback_new_package(
            final_dir,
            ftp_host="fake-host",
            ftp_user="fake-user",
            ftp_password="fake-password",
            ftp_factory=server.client,
        )

        self.assertNotIn(final_dir, server.directories)
        self.assertEqual(b"old package", server.files[f"{old_dir}/old.txt"])

    def test_rejects_unsafe_or_ambiguous_course_code(self):
        for course_code in ("", ".", "..", "../curso", "curso/parte", " curso", "curso "):
            with self.subTest(course_code=course_code):
                with self.assertRaises(ScormPublishError) as raised:
                    validate_course_code_component(course_code)
                self.assertEqual("invalid_course_code", raised.exception.code)
