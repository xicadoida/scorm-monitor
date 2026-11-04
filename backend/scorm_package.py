"""Validação e extração segura de pacotes SCORM em ZIP.

O módulo não interpreta a lógica pedagógica do pacote. Ele apenas garante que
o arquivo possa ser extraído com segurança e preserve o contrato estrutural
já aceito pelo LMS: exatamente um ``imsmanifest.xml`` e o launcher
``scormdriver/indexAPI.html`` na mesma raiz.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
from typing import Any
import zipfile


UPLOAD_CHUNK_SIZE = 64 * 1024
EXTRACT_CHUNK_SIZE = 64 * 1024
MAX_PATH_LENGTH = 512
MAX_PATH_COMPONENT_LENGTH = 255
SUPPORTED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class ScormPackageError(ValueError):
    """Erro previsível ao receber, validar ou extrair um pacote SCORM."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ScormPackageLimits:
    """Limites de recurso aplicados a cada pacote recebido."""

    max_upload_bytes: int = 100 * 1024 * 1024
    max_entries: int = 5_000
    max_uncompressed_bytes: int = 512 * 1024 * 1024
    max_file_bytes: int = 100 * 1024 * 1024
    max_compression_ratio: float = 100.0

    @classmethod
    def from_environment(cls) -> "ScormPackageLimits":
        return cls(
            max_upload_bytes=_positive_int("SCORM_MAX_UPLOAD_BYTES", cls.max_upload_bytes),
            max_entries=_positive_int("SCORM_MAX_ENTRIES", cls.max_entries),
            max_uncompressed_bytes=_positive_int(
                "SCORM_MAX_UNCOMPRESSED_BYTES", cls.max_uncompressed_bytes
            ),
            max_file_bytes=_positive_int("SCORM_MAX_FILE_BYTES", cls.max_file_bytes),
            max_compression_ratio=_positive_float(
                "SCORM_MAX_COMPRESSION_RATIO", cls.max_compression_ratio
            ),
        )


@dataclass(frozen=True)
class ScormPackage:
    """Resultado de uma extração SCORM validada."""

    root_dir: Path
    manifest_path: Path
    launcher_path: Path
    entry_count: int
    compressed_bytes: int
    uncompressed_bytes: int


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _validate_limits(limits: ScormPackageLimits) -> None:
    values = (
        limits.max_upload_bytes,
        limits.max_entries,
        limits.max_uncompressed_bytes,
        limits.max_file_bytes,
        limits.max_compression_ratio,
    )
    if any(value <= 0 for value in values):
        raise ValueError("Os limites do pacote SCORM devem ser positivos.")


async def save_upload_to_path(
    upload: Any,
    destination: str | Path,
    limits: ScormPackageLimits | None = None,
) -> int:
    """Persiste o upload em blocos e aplica o limite ao ZIP recebido."""

    limits = limits or ScormPackageLimits.from_environment()
    _validate_limits(limits)
    target = Path(destination)
    bytes_written = 0
    created_target = False

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            created_target = True
            while True:
                chunk = await upload.read(UPLOAD_CHUNK_SIZE)
                if chunk == b"":
                    break
                if not isinstance(chunk, (bytes, bytearray)):
                    raise ScormPackageError(
                        "upload_read_failed",
                        "Não foi possível ler o arquivo enviado.",
                    )

                bytes_written += len(chunk)
                if bytes_written > limits.max_upload_bytes:
                    raise ScormPackageError(
                        "upload_too_large",
                        "O ZIP excede o tamanho máximo permitido para pacotes SCORM.",
                    )
                stream.write(chunk)

        if bytes_written == 0:
            raise ScormPackageError("empty_upload", "O arquivo ZIP enviado está vazio.")
        return bytes_written
    except ScormPackageError:
        if created_target:
            target.unlink(missing_ok=True)
        raise
    except OSError as error:
        if created_target:
            target.unlink(missing_ok=True)
        raise ScormPackageError(
            "upload_write_failed",
            "Não foi possível salvar temporariamente o ZIP enviado.",
        ) from error


def validate_and_extract_scorm(
    archive_path: str | Path,
    extraction_dir: str | Path,
    limits: ScormPackageLimits | None = None,
) -> ScormPackage:
    """Valida o índice ZIP e extrai o conteúdo sem usar ``extractall``.

    ``extraction_dir`` deve ainda não existir. Dessa forma, em qualquer falha,
    somente uma pasta temporária criada por esta função é removida.
    """

    limits = limits or ScormPackageLimits.from_environment()
    _validate_limits(limits)
    source = Path(archive_path)
    destination = Path(extraction_dir)

    try:
        archive_size = source.stat().st_size
    except OSError as error:
        raise ScormPackageError(
            "archive_unavailable", "Não foi possível acessar o ZIP enviado."
        ) from error

    if archive_size <= 0:
        raise ScormPackageError("empty_upload", "O arquivo ZIP enviado está vazio.")
    if archive_size > limits.max_upload_bytes:
        raise ScormPackageError(
            "upload_too_large",
            "O ZIP excede o tamanho máximo permitido para pacotes SCORM.",
        )
    if destination.exists():
        raise ScormPackageError(
            "extraction_target_exists",
            "Não foi possível preparar a área temporária para o pacote SCORM.",
        )

    try:
        destination.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        raise ScormPackageError(
            "extraction_target_failed",
            "Não foi possível preparar a área temporária para o pacote SCORM.",
        ) from error

    try:
        with zipfile.ZipFile(source, "r") as archive:
            members, compressed_bytes, uncompressed_bytes = _validate_archive_index(
                archive.infolist(), limits
            )
            _extract_members(archive, members, destination, limits)
            manifest_path, launcher_path = _find_scorm_files(destination)

        return ScormPackage(
            root_dir=manifest_path.parent,
            manifest_path=manifest_path,
            launcher_path=launcher_path,
            entry_count=len(members),
            compressed_bytes=compressed_bytes,
            uncompressed_bytes=uncompressed_bytes,
        )
    except ScormPackageError:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    except (
        OSError,
        RuntimeError,
        EOFError,
        NotImplementedError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as error:
        shutil.rmtree(destination, ignore_errors=True)
        raise ScormPackageError(
            "invalid_zip",
            "Envie um arquivo ZIP SCORM válido e íntegro.",
        ) from error


def _validate_archive_index(
    entries: list[zipfile.ZipInfo], limits: ScormPackageLimits
) -> tuple[list[tuple[zipfile.ZipInfo, str, bool]], int, int]:
    if len(entries) > limits.max_entries:
        raise ScormPackageError(
            "too_many_entries",
            "O ZIP possui arquivos demais para um pacote SCORM permitido.",
        )

    normalized_entries: list[tuple[zipfile.ZipInfo, str, bool]] = []
    seen_paths: dict[str, str] = {}
    file_paths: set[str] = set()
    compressed_bytes = 0
    uncompressed_bytes = 0

    for entry in entries:
        safe_name, is_directory = _validate_member(entry)
        if entry.compress_type not in SUPPORTED_COMPRESSION_METHODS:
            raise ScormPackageError(
                "unsupported_compression",
                "O ZIP usa um método de compressão não suportado para pacotes SCORM.",
            )
        comparison_name = safe_name.casefold()
        existing = seen_paths.get(comparison_name)
        if existing is not None:
            raise ScormPackageError(
                "conflicting_entries",
                "O ZIP possui nomes de arquivos duplicados ou conflitantes.",
            )
        seen_paths[comparison_name] = safe_name

        if not is_directory:
            if entry.file_size > limits.max_file_bytes:
                raise ScormPackageError(
                    "file_too_large",
                    "Um arquivo do pacote SCORM excede o tamanho permitido.",
                )
            uncompressed_bytes += entry.file_size
            compressed_bytes += entry.compress_size
            if uncompressed_bytes > limits.max_uncompressed_bytes:
                raise ScormPackageError(
                    "uncompressed_too_large",
                    "O conteúdo descompactado do ZIP excede o limite permitido.",
                )
            if compressed_bytes > limits.max_upload_bytes:
                raise ScormPackageError(
                    "compressed_too_large",
                    "O conteúdo compactado do ZIP excede o limite permitido.",
                )
            if entry.file_size > 0:
                if entry.compress_size <= 0:
                    raise ScormPackageError(
                        "suspicious_compression",
                        "O ZIP possui uma entrada com compressão inválida.",
                    )
                ratio = entry.file_size / entry.compress_size
                if ratio > limits.max_compression_ratio:
                    raise ScormPackageError(
                        "compression_ratio_too_large",
                        "O ZIP possui uma taxa de expansão acima do limite permitido.",
                    )
            file_paths.add(safe_name)

        normalized_entries.append((entry, safe_name, is_directory))

    for _, safe_name, _ in normalized_entries:
        parts = safe_name.split("/")
        for position in range(1, len(parts)):
            if "/".join(parts[:position]) in file_paths:
                raise ScormPackageError(
                    "file_directory_conflict",
                    "O ZIP possui um arquivo que conflita com uma pasta do pacote.",
                )

    return normalized_entries, compressed_bytes, uncompressed_bytes


def _validate_member(entry: zipfile.ZipInfo) -> tuple[str, bool]:
    name = entry.filename
    if not isinstance(name, str) or not name:
        raise ScormPackageError("invalid_entry_name", "O ZIP possui uma entrada sem nome válido.")
    if len(name) > MAX_PATH_LENGTH:
        raise ScormPackageError("path_too_long", "O ZIP possui um caminho de arquivo longo demais.")
    if "\x00" in name or any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ScormPackageError("invalid_entry_name", "O ZIP possui um nome de arquivo inválido.")
    if "\\" in name or name.startswith("/") or _looks_like_windows_path(name):
        raise ScormPackageError("unsafe_path", "O ZIP possui um caminho de arquivo inseguro.")
    if entry.flag_bits & 0x1:
        raise ScormPackageError("encrypted_entry", "ZIPs SCORM criptografados não são permitidos.")

    is_directory = entry.is_dir()
    normalized_name = name[:-1] if is_directory else name
    parts = normalized_name.split("/")
    if not normalized_name or any(
        not part or part in {".", ".."} or len(part) > MAX_PATH_COMPONENT_LENGTH
        for part in parts
    ):
        raise ScormPackageError("unsafe_path", "O ZIP possui um caminho de arquivo inseguro.")

    mode = (entry.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    if stat.S_ISLNK(mode):
        raise ScormPackageError("unsupported_entry", "Links simbólicos não são permitidos em ZIPs SCORM.")
    # ZIPs criados em Windows ou pelo próprio ``writestr`` podem ter apenas
    # bits de permissão, sem o tipo POSIX. Esses arquivos são válidos.
    if file_type and file_type not in {stat.S_IFREG, stat.S_IFDIR}:
        raise ScormPackageError(
            "unsupported_entry", "O ZIP possui um tipo de arquivo não suportado."
        )
    if (
        (is_directory and file_type == stat.S_IFREG)
        or (not is_directory and file_type == stat.S_IFDIR)
    ):
        raise ScormPackageError(
            "invalid_directory", "O ZIP possui uma pasta com conteúdo inválido."
        )
    if is_directory and entry.file_size:
        raise ScormPackageError(
            "invalid_directory", "O ZIP possui uma pasta com conteúdo inválido."
        )

    return "/".join(parts), is_directory


def _looks_like_windows_path(name: str) -> bool:
    return len(name) >= 2 and name[0].isalpha() and name[1] == ":"


def _extract_members(
    archive: zipfile.ZipFile,
    members: list[tuple[zipfile.ZipInfo, str, bool]],
    destination: Path,
    limits: ScormPackageLimits,
) -> None:
    root = destination.resolve()
    actual_uncompressed_bytes = 0

    for entry, safe_name, is_directory in members:
        target = destination.joinpath(*safe_name.split("/"))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.resolve().relative_to(root)
        except (OSError, ValueError) as error:
            raise ScormPackageError(
                "unsafe_path", "O ZIP possui um caminho de arquivo inseguro."
            ) from error

        if is_directory:
            try:
                target.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise ScormPackageError(
                    "extraction_failed", "Não foi possível extrair o ZIP SCORM."
                ) from error
            continue

        extracted_for_file = 0
        try:
            with archive.open(entry, "r") as source, target.open("xb") as output:
                while True:
                    chunk = source.read(EXTRACT_CHUNK_SIZE)
                    if not chunk:
                        break
                    extracted_for_file += len(chunk)
                    actual_uncompressed_bytes += len(chunk)
                    if extracted_for_file > limits.max_file_bytes:
                        raise ScormPackageError(
                            "file_too_large",
                            "Um arquivo do pacote SCORM excede o tamanho permitido.",
                        )
                    if actual_uncompressed_bytes > limits.max_uncompressed_bytes:
                        raise ScormPackageError(
                            "uncompressed_too_large",
                            "O conteúdo descompactado do ZIP excede o limite permitido.",
                        )
                    output.write(chunk)
        except ScormPackageError:
            raise
        except (OSError, RuntimeError, EOFError, NotImplementedError, zipfile.BadZipFile) as error:
            raise ScormPackageError(
                "extraction_failed", "Não foi possível extrair o ZIP SCORM."
            ) from error

        if extracted_for_file != entry.file_size:
            raise ScormPackageError(
                "invalid_zip", "O ZIP possui uma entrada com tamanho inválido."
            )


def _find_scorm_files(extraction_dir: Path) -> tuple[Path, Path]:
    manifests = [
        candidate
        for candidate in extraction_dir.rglob("imsmanifest.xml")
        if candidate.is_file()
    ]
    if not manifests:
        raise ScormPackageError(
            "manifest_missing", "Arquivo inválido: nenhum imsmanifest.xml encontrado."
        )
    if len(manifests) > 1:
        raise ScormPackageError(
            "manifest_duplicated", "Arquivo inválido: o ZIP contém mais de um pacote SCORM."
        )

    manifest_path = manifests[0]
    launcher_path = manifest_path.parent / "scormdriver" / "indexAPI.html"
    if not launcher_path.is_file():
        raise ScormPackageError(
            "launcher_missing",
            "Arquivo inválido: scormdriver/indexAPI.html não encontrado.",
        )
    return manifest_path, launcher_path
