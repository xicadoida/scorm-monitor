"""Publicação FTP de pacotes SCORM já validados.

O upload acontece primeiro em uma pasta remota de staging. A pasta publicada
somente é trocada após a cópia completa, e uma substituição mantém backup até o
backend confirmar a atualização local.
"""

from __future__ import annotations

from dataclasses import dataclass
import ftplib
import os
from pathlib import Path
import uuid
from typing import Callable


class ScormPublishError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RemoteReplacement:
    final_dir: str
    backup_dir: str | None


def validate_course_code_component(course_code: str) -> str:
    """Garante que o código ocupe somente um segmento de caminho FTP."""

    if not isinstance(course_code, str):
        raise ScormPublishError("invalid_course_code", "O código do curso é inválido.")
    normalized = course_code.strip()
    if (
        course_code != normalized
        or not normalized
        or len(normalized) > 100
        or normalized in {".", ".."}
        or any(character in normalized for character in ("/", "\\", "\x00"))
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ScormPublishError(
            "invalid_course_code", "O código do curso contém caracteres não permitidos."
        )
    return normalized


def publish_new_package(
    local_dir: str | Path,
    *,
    course_code: str,
    ftp_host: str,
    ftp_user: str,
    ftp_password: str | None,
    ftp_base_dir: str,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> str:
    """Publica um curso novo sem sobrescrever uma pasta já publicada."""

    code = validate_course_code_component(course_code)
    final_dir = _remote_path(ftp_base_dir, code)
    staging_dir = _staging_dir(ftp_base_dir, code)
    ftp = _connect(ftp_factory, ftp_host, ftp_user, ftp_password)

    try:
        if _remote_child_exists(ftp, ftp_base_dir, code):
            raise ScormPublishError(
                "remote_course_exists", "Já existe uma pasta publicada para este código de curso."
            )
        upload_directory(ftp, Path(local_dir), staging_dir)
        ftp.rename(staging_dir, final_dir)
        return final_dir
    except ScormPublishError:
        _cleanup_remote_tree(ftp, staging_dir)
        raise
    except Exception as error:
        _cleanup_remote_tree(ftp, staging_dir)
        raise ScormPublishError(
            "publish_failed", "Não foi possível publicar o pacote SCORM."
        ) from error
    finally:
        _safe_quit(ftp)


def replace_published_package(
    local_dir: str | Path,
    *,
    course_code: str,
    ftp_host: str,
    ftp_user: str,
    ftp_password: str | None,
    ftp_base_dir: str,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> RemoteReplacement:
    """Troca um pacote publicado ou recupera uma pasta remota ausente."""

    code = validate_course_code_component(course_code)
    final_dir = _remote_path(ftp_base_dir, code)
    staging_dir = _staging_dir(ftp_base_dir, code)
    backup_dir = _backup_dir(ftp_base_dir, code)
    ftp = _connect(ftp_factory, ftp_host, ftp_user, ftp_password)
    moved_current_to_backup = False

    try:
        has_current_package = _remote_child_exists(ftp, ftp_base_dir, code)
        upload_directory(ftp, Path(local_dir), staging_dir)
        if not has_current_package:
            # Um curso pode existir no banco enquanto sua pasta FTP foi apagada
            # manualmente. O upload de substituição também deve poder repará-lo,
            # sem confundir uma falha de listagem com uma pasta ausente.
            ftp.rename(staging_dir, final_dir)
            return RemoteReplacement(final_dir=final_dir, backup_dir=None)

        ftp.rename(final_dir, backup_dir)
        moved_current_to_backup = True
        try:
            ftp.rename(staging_dir, final_dir)
        except Exception as error:
            try:
                _restore_backup(ftp, final_dir, backup_dir)
            except ScormPublishError as restore_error:
                moved_current_to_backup = False
                _cleanup_remote_tree(ftp, staging_dir)
                raise restore_error from error
            moved_current_to_backup = False
            raise ScormPublishError(
                "publish_swap_failed",
                "Não foi possível trocar o pacote SCORM sem risco ao pacote anterior.",
            ) from error
        return RemoteReplacement(final_dir=final_dir, backup_dir=backup_dir)
    except ScormPublishError:
        if moved_current_to_backup:
            _restore_backup(ftp, final_dir, backup_dir)
        _cleanup_remote_tree(ftp, staging_dir)
        raise
    except Exception as error:
        if moved_current_to_backup:
            _restore_backup(ftp, final_dir, backup_dir)
        _cleanup_remote_tree(ftp, staging_dir)
        raise ScormPublishError(
            "publish_failed", "Não foi possível publicar o pacote SCORM."
        ) from error
    finally:
        _safe_quit(ftp)


def finalize_replacement(
    replacement: RemoteReplacement,
    *,
    ftp_host: str,
    ftp_user: str,
    ftp_password: str | None,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> None:
    """Remove o backup remoto somente depois de confirmado o commit local."""

    if replacement.backup_dir is None:
        return

    ftp = _connect(ftp_factory, ftp_host, ftp_user, ftp_password)
    try:
        remove_remote_tree(ftp, replacement.backup_dir)
    except Exception as error:
        raise ScormPublishError(
            "backup_cleanup_failed",
            "O novo pacote foi publicado, mas não foi possível remover o backup temporário.",
        ) from error
    finally:
        _safe_quit(ftp)


def rollback_new_package(
    final_dir: str,
    *,
    ftp_host: str,
    ftp_user: str,
    ftp_password: str | None,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> None:
    """Compensa uma publicação nova quando o banco não confirma o curso."""

    ftp = _connect(ftp_factory, ftp_host, ftp_user, ftp_password)
    try:
        remove_remote_tree(ftp, final_dir)
    except Exception as error:
        raise ScormPublishError(
            "publish_rollback_failed",
            "Não foi possível remover a publicação temporária do curso.",
        ) from error
    finally:
        _safe_quit(ftp)


def rollback_replacement(
    replacement: RemoteReplacement,
    *,
    ftp_host: str,
    ftp_user: str,
    ftp_password: str | None,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> None:
    """Restaura a versão anterior quando a atualização local falha."""

    ftp = _connect(ftp_factory, ftp_host, ftp_user, ftp_password)
    rollback_dir = _rollback_dir(replacement.final_dir)
    try:
        if replacement.backup_dir is None:
            remove_remote_tree(ftp, replacement.final_dir)
            return

        # Nunca apaga a versão nova antes de saber que a antiga voltou a ocupar
        # o caminho final. Se a troca falhar, tenta recolocar a versão nova.
        try:
            ftp.rename(replacement.final_dir, rollback_dir)
        except Exception as error:
            raise ScormPublishError(
                "replacement_rollback_prepare_failed",
                "Não foi possível iniciar a restauração do pacote SCORM anterior.",
            ) from error

        try:
            ftp.rename(replacement.backup_dir, replacement.final_dir)
        except Exception as error:
            try:
                ftp.rename(rollback_dir, replacement.final_dir)
            except Exception as restore_error:
                raise ScormPublishError(
                    "replacement_rollback_restore_failed",
                    "Não foi possível restaurar uma versão disponível do pacote SCORM.",
                ) from restore_error
            raise ScormPublishError(
                "replacement_rollback_swap_failed",
                "Não foi possível restaurar o pacote anterior; o pacote novo foi mantido.",
            ) from error

        try:
            remove_remote_tree(ftp, rollback_dir)
        except Exception as error:
            raise ScormPublishError(
                "replacement_rollback_cleanup_failed",
                "O pacote anterior foi restaurado, mas a versão temporária não foi removida.",
            ) from error
    except ScormPublishError:
        raise
    except Exception as error:
        raise ScormPublishError(
            "replacement_rollback_failed",
            "Não foi possível restaurar o pacote SCORM anterior.",
        ) from error
    finally:
        _safe_quit(ftp)


def upload_directory(ftp: ftplib.FTP, local_dir: Path, remote_dir: str) -> None:
    """Envia uma árvore local para uma pasta remota nova de staging."""

    try:
        ftp.mkd(remote_dir)
    except Exception as error:
        raise ScormPublishError(
            "staging_create_failed", "Não foi possível preparar a publicação temporária do SCORM."
        ) from error

    for item_name in sorted(os.listdir(local_dir)):
        local_path = local_dir / item_name
        remote_path = f"{remote_dir}/{item_name}"
        if local_path.is_dir():
            upload_directory(ftp, local_path, remote_path)
        else:
            with local_path.open("rb") as stream:
                ftp.storbinary(f"STOR {remote_path}", stream)


def remove_remote_tree(ftp: ftplib.FTP, remote_dir: str) -> bool:
    """Remove uma pasta FTP e seu conteúdo; ausência da pasta é aceitável."""

    try:
        items = ftp.nlst(remote_dir)
    except ftplib.error_perm:
        return False

    for item in items:
        if item.rstrip("/") == remote_dir.rstrip("/"):
            continue
        name = item.rsplit("/", 1)[-1]
        if name in {".", ".."}:
            continue
        if not name or "\\" in name or "/" in name:
            raise ScormPublishError(
                "remote_listing_invalid",
                "O armazenamento retornou uma listagem de arquivos inválida.",
            )
        # Use only the direct entry name so a malformed FTP response cannot
        # direct deletion outside the package directory.
        item_path = f"{remote_dir.rstrip('/')}/{name}"
        try:
            ftp.delete(item_path)
        except ftplib.error_perm:
            remove_remote_tree(ftp, item_path)

    ftp.rmd(remote_dir)
    return True


def _connect(
    ftp_factory: Callable[[], ftplib.FTP],
    host: str,
    user: str,
    password: str | None,
) -> ftplib.FTP:
    ftp = ftp_factory()
    try:
        ftp.connect(host, 21, timeout=10)
        ftp.login(user, password)
        return ftp
    except Exception as error:
        _safe_quit(ftp)
        raise ScormPublishError(
            "ftp_connection_failed", "Não foi possível conectar ao armazenamento do SCORM."
        ) from error


def _remote_child_exists(ftp: ftplib.FTP, parent_dir: str, child_name: str) -> bool:
    try:
        children = ftp.nlst(parent_dir)
    except Exception as error:
        raise ScormPublishError(
            "remote_listing_failed", "Não foi possível verificar o destino do pacote SCORM."
        ) from error
    expected = _remote_path(parent_dir, child_name)
    return any(item.rstrip("/") == expected or item.rsplit("/", 1)[-1] == child_name for item in children)


def _staging_dir(base_dir: str, course_code: str) -> str:
    return _remote_path(base_dir, f".{course_code}.staging-{uuid.uuid4().hex}")


def _backup_dir(base_dir: str, course_code: str) -> str:
    return _remote_path(base_dir, f".{course_code}.backup-{uuid.uuid4().hex}")


def _rollback_dir(final_dir: str) -> str:
    return f"{final_dir}.rollback-{uuid.uuid4().hex}"


def _remote_path(base_dir: str, component: str) -> str:
    return f"{base_dir.rstrip('/')}/{component}"


def _cleanup_remote_tree(ftp: ftplib.FTP, remote_dir: str) -> None:
    try:
        remove_remote_tree(ftp, remote_dir)
    except Exception:
        return


def _restore_backup(ftp: ftplib.FTP, final_dir: str, backup_dir: str) -> None:
    try:
        remove_remote_tree(ftp, final_dir)
        ftp.rename(backup_dir, final_dir)
    except Exception as error:
        raise ScormPublishError(
            "backup_restore_failed",
            "Não foi possível restaurar o pacote SCORM anterior.",
        ) from error


def _safe_quit(ftp: ftplib.FTP) -> None:
    try:
        ftp.quit()
    except Exception:
        return
