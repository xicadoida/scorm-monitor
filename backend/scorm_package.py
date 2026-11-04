"""Validação local compartilhada; não publica arquivos nem acessa o banco."""
import os
import re
import stat
import zipfile
import zlib
from pathlib import Path
from scorm_manifest import InvalidManifest, validate_manifest


class InvalidPackage(ValueError):
    pass


def limit(name, default):
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} deve ser positivo")
    return value


def validate_course_code(code):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", code):
        raise InvalidPackage("Código do curso inválido: use letras, números, _ ou -.")


async def prepare_package(upload, directory):
    """Limita leitura, valida todas as entradas e só então extrai em pasta nova."""
    archive = Path(directory) / "package.zip"
    maximum = limit("SCORM_MAX_UPLOAD_BYTES", 100 * 1024 * 1024)
    size = 0
    with archive.open("wb") as target:
        while chunk := await upload.read(64 * 1024):
            size += len(chunk)
            if size > maximum:
                raise InvalidPackage("ZIP excede o limite de upload.")
            target.write(chunk)
    return extract_package(archive, Path(directory) / "content")


def extract_package(archive, destination):
    maximum = limit("SCORM_MAX_EXTRACTED_BYTES", 500 * 1024 * 1024)
    per_file = limit("SCORM_MAX_FILE_BYTES", 100 * 1024 * 1024)
    entries = limit("SCORM_MAX_ENTRIES", 10000)
    ratio = limit("SCORM_MAX_EXPANSION_RATIO", 200)
    destination = Path(destination)
    try:
        with zipfile.ZipFile(archive) as package:
            items = package.infolist()
            if len(items) > entries:
                raise InvalidPackage("ZIP excede o limite de entradas.")
            names = set()
            total = 0
            manifests = []
            for item in items:
                name = item.filename.rstrip("/")
                parts = name.split("/")
                # Rejeita também aliases e caminhos especiais do Windows.
                if (not name or "\\" in item.orig_filename or "\x00" in item.orig_filename or name.startswith("/")
                        or any(p in {"", ".", ".."} or ":" in p
                               or p.endswith((".", " "))
                               or re.search(r'[<>"|?*\x00-\x1f]', p)
                               or p.split(".")[0].upper() in {
                                   "CON", "PRN", "AUX", "NUL",
                                   *(f"COM{i}" for i in range(1, 10)),
                                   *(f"LPT{i}" for i in range(1, 10)),
                               } for p in parts)):
                    raise InvalidPackage("ZIP contém caminho inseguro.")
                key = name.casefold()
                if key in names:
                    raise InvalidPackage("ZIP contém caminhos duplicados.")
                names.add(key)
                mode = item.external_attr >> 16
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise InvalidPackage("ZIP contém link ou arquivo especial.")
                if item.flag_bits & 1:
                    raise InvalidPackage("ZIP criptografado não é aceito.")
                if Path(name).suffix.lower() in {".php", ".phtml", ".phar", ".cgi", ".asp", ".aspx", ".exe", ".sh", ".bat", ".cmd"} or any(p.startswith(".") for p in parts):
                    raise InvalidPackage("ZIP contém arquivo não permitido.")
                total += item.file_size
                if (item.file_size > per_file or total > maximum
                        or item.file_size > max(item.compress_size, 1) * ratio):
                    raise InvalidPackage("ZIP excede os limites de extração.")
                if not item.is_dir() and parts[-1] == "imsmanifest.xml":
                    manifests.append(name)
            if len(manifests) != 1:
                raise InvalidPackage("ZIP deve conter exatamente um imsmanifest.xml.")
            root = Path(manifests[0]).parent
            # Uma pasta exclusiva evita que arquivos do ZIP sobrescrevam o próprio ZIP.
            destination.mkdir(exist_ok=False)
            actual_total = 0
            for item in items:
                target = destination.joinpath(*item.filename.rstrip("/").split("/"))
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                actual_file = 0
                with package.open(item) as source, target.open("xb") as output:
                    while chunk := source.read(64 * 1024):
                        actual_file += len(chunk)
                        actual_total += len(chunk)
                        if actual_file > per_file or actual_total > maximum:
                            raise InvalidPackage("ZIP excede os limites de extração.")
                        output.write(chunk)
            try:
                validate_manifest(destination / root, limit('SCORM_MAX_MANIFEST_BYTES', 2 * 1024 * 1024))
            except (InvalidManifest, ValueError) as error:
                raise InvalidPackage(str(error)) from error
            return str(destination / root)
    except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError, OSError) as error:
        raise InvalidPackage("Envie um ZIP SCORM íntegro e compatível.") from error
