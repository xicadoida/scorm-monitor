from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from database import SessionLocal
from models import Course, Enrollment, CourseSession
from schemas import CourseCreateRequest, CourseUpdateRequest
from catalog_utils import touch_catalog
from auth_utils import CurrentUser, get_current_user, require_admin
from scorm_package import ScormPackageError, save_upload_to_path, validate_and_extract_scorm
from scorm_publisher import (
    ScormPublishError,
    finalize_replacement,
    publish_new_package,
    replace_published_package,
    rollback_new_package,
    rollback_replacement,
    validate_course_code_component,
)

import os
import ftplib
import tempfile

router = APIRouter()

FTP_HOST = "147.93.37.72"
FTP_USER = "u124251760.lms.iaclube.help"
FTP_PASS = os.getenv("FTP_PASSWORD")
FTP_BASE_DIR = "/public_html/scorm"
PUBLIC_BASE_URL = "https://lms.iaclube.help/scorm"
CATALOG_STATUSES = {"active", "coming_soon", "completed"}


def remove_dir_ftp(ftp, remote_dir):
    try:
        items = ftp.nlst(remote_dir)
    except ftplib.error_perm:
        return

    for item in items:
        name = item.split("/")[-1]

        if name in (".", ".."):
            continue

        item_path = f"{remote_dir}/{name}"

        try:
            ftp.delete(item_path)
        except ftplib.error_perm:
            remove_dir_ftp(ftp, item_path)

    try:
        ftp.rmd(remote_dir)
    except ftplib.error_perm:
        pass


@router.post("/courses/upload")
async def upload_course(
    title: str = Form(...),
    course_code: str = Form(...),
    file: UploadFile = File(...),
    event_id: Optional[int] = Form(None),
    color_primary: Optional[str] = Form(None),
    passing_score: Optional[int] = Form(80),
    tool: Optional[str] = Form(None),
    duration_hours: Optional[int] = Form(None),
    catalog_url: Optional[str] = Form(None),
    thumbnail_url: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    catalog_status: Optional[str] = Form("active"),
    _: CurrentUser = Depends(require_admin),
):
    if catalog_status not in CATALOG_STATUSES:
        return {"success": False, "message": "Status de catálogo inválido."}
    try:
        safe_course_code = validate_course_code_component(course_code)
    except ScormPublishError as error:
        return {"success": False, "message": str(error)}

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_root = Path(tmp_dir)
        try:
            await save_upload_to_path(file, temp_root / "source.zip")
            package = validate_and_extract_scorm(
                temp_root / "source.zip", temp_root / "extracted"
            )
        except ScormPackageError as error:
            return {"success": False, "message": str(error)}

        db = SessionLocal()
        try:
            existing_course = db.query(Course).filter(
                Course.course_code == safe_course_code
            ).first()
        finally:
            db.close()
        if existing_course:
            return {"success": False, "message": "Já existe um curso com este código."}

        try:
            remote_course_dir = publish_new_package(
                package.root_dir,
                course_code=safe_course_code,
                ftp_host=FTP_HOST,
                ftp_user=FTP_USER,
                ftp_password=FTP_PASS,
                ftp_base_dir=FTP_BASE_DIR,
            )
        except ScormPublishError as error:
            return {"success": False, "message": str(error)}

        scorm_path = f"{PUBLIC_BASE_URL}/{safe_course_code}/scormdriver/indexAPI.html"
        resolved_passing_score = passing_score or 80
        db = SessionLocal()
        try:
            course = Course(
                title=title,
                course_code=safe_course_code,
                scorm_path=scorm_path,
                active=True,
                event_id=event_id,
                color_primary=color_primary,
                passing_score=resolved_passing_score,
                tool=tool,
                duration_hours=duration_hours,
                catalog_url=catalog_url,
                thumbnail_url=thumbnail_url,
                short_description=short_description,
                catalog_status=catalog_status,
                created_at=datetime.utcnow(),
            )
            db.add(course)
            db.flush()
            course_id = course.id
            touch_catalog(db)
            db.commit()
        except Exception:
            db.rollback()
            rollback_failed = False
            try:
                rollback_new_package(
                    remote_course_dir,
                    ftp_host=FTP_HOST,
                    ftp_user=FTP_USER,
                    ftp_password=FTP_PASS,
                )
            except ScormPublishError:
                rollback_failed = True
            return {
                "success": False,
                "message": (
                    "Não foi possível registrar o curso após publicar o SCORM. "
                    "A publicação temporária pode exigir verificação manual."
                    if rollback_failed
                    else "Não foi possível registrar o curso após publicar o SCORM."
                ),
            }
        finally:
            db.close()

        return {
            "id": course_id,
            "title": title,
            "course_code": safe_course_code,
            "scorm_path": scorm_path,
            "event_id": event_id,
            "color_primary": color_primary,
            "passing_score": resolved_passing_score,
            "catalog_status": catalog_status,
            "message": "Course uploaded successfully",
        }


@router.post("/courses/{course_code}/replace-file")
async def replace_course_file(
    course_code: str,
    file: UploadFile = File(...),
    _: CurrentUser = Depends(require_admin),
):
    """Substitui somente o pacote SCORM, preservando todos os vínculos do curso."""
    try:
        safe_course_code = validate_course_code_component(course_code)
    except ScormPublishError as error:
        return {"success": False, "message": str(error)}

    db = SessionLocal()
    course = db.query(Course).filter(Course.course_code == safe_course_code).first()
    if not course:
        db.close()
        return {"success": False, "message": "Curso não encontrado."}

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_root = Path(tmp_dir)
        try:
            await save_upload_to_path(file, temp_root / "source.zip")
            package = validate_and_extract_scorm(
                temp_root / "source.zip", temp_root / "extracted"
            )
        except ScormPackageError as error:
            db.close()
            return {"success": False, "message": str(error)}

        try:
            replacement = replace_published_package(
                package.root_dir,
                course_code=safe_course_code,
                ftp_host=FTP_HOST,
                ftp_user=FTP_USER,
                ftp_password=FTP_PASS,
                ftp_base_dir=FTP_BASE_DIR,
            )
        except ScormPublishError as error:
            db.close()
            return {"success": False, "message": str(error)}

        try:
            course.updated_at = datetime.utcnow()
            touch_catalog(db)
            db.commit()
        except Exception:
            db.rollback()
            rollback_failed = False
            try:
                rollback_replacement(
                    replacement,
                    ftp_host=FTP_HOST,
                    ftp_user=FTP_USER,
                    ftp_password=FTP_PASS,
                )
            except ScormPublishError:
                rollback_failed = True
            db.close()
            return {
                "success": False,
                "message": (
                    "Não foi possível registrar a substituição do arquivo SCORM. "
                    "O pacote anterior pode exigir restauração manual."
                    if rollback_failed
                    else "Não foi possível registrar a substituição do arquivo SCORM."
                ),
            }
        db.close()

    ftp_warning = None
    try:
        finalize_replacement(
            replacement,
            ftp_host=FTP_HOST,
            ftp_user=FTP_USER,
            ftp_password=FTP_PASS,
        )
    except ScormPublishError as error:
        ftp_warning = str(error)

    return {
        "success": True,
        "message": "Arquivo SCORM substituído. Progresso, conclusões e presenças foram preservados.",
        "ftp_warning": ftp_warning,
    }


@router.post("/courses")
def create_course(data: CourseCreateRequest, _: CurrentUser = Depends(require_admin)):
    if data.catalog_status not in CATALOG_STATUSES:
        return {"success": False, "message": "Status de catálogo inválido."}

    db = SessionLocal()

    course = Course(
        title=data.title,
        course_code=data.course_code,
        scorm_path=data.scorm_path,
        active=True,
        event_id=data.event_id,
        color_primary=data.color_primary,
        passing_score=data.passing_score or 80,
        tool=data.tool,
        duration_hours=data.duration_hours,
        catalog_url=data.catalog_url,
        thumbnail_url=data.thumbnail_url,
        short_description=data.short_description,
        catalog_status=data.catalog_status,
        created_at=datetime.utcnow()
    )

    db.add(course)
    touch_catalog(db)
    db.commit()
    db.refresh(course)
    db.close()

    return {
        "id": course.id,
        "title": course.title,
        "course_code": course.course_code,
        "scorm_path": course.scorm_path,
        "active": course.active,
        "event_id": course.event_id,
        "color_primary": course.color_primary
        ,"passing_score": course.passing_score,
        "tool": course.tool,
        "duration_hours": course.duration_hours,
        "catalog_url": course.catalog_url,
        "thumbnail_url": course.thumbnail_url,
        "short_description": course.short_description,
        "catalog_status": course.catalog_status,
    }


@router.get("/courses")
def list_courses(_: CurrentUser = Depends(require_admin)):
    db = SessionLocal()
    courses = db.query(Course).all()

    result = [
        {
            "id": c.id,
            "title": c.title,
            "course_code": c.course_code,
            "scorm_path": c.scorm_path,
            "active": c.active,
            "event_id": c.event_id,
            "color_primary": c.color_primary,
            "passing_score": c.passing_score,
            "tool": c.tool,
            "duration_hours": c.duration_hours,
            "catalog_url": c.catalog_url,
            "thumbnail_url": c.thumbnail_url,
            "short_description": c.short_description,
            "catalog_status": c.catalog_status,
            "created_at": c.created_at
        }
        for c in courses
    ]

    db.close()
    return result


@router.get("/courses/public")
def list_public_courses(email: str, current_user: CurrentUser = Depends(get_current_user)):
    """
    Lista usada na aba 'Todos Cursos'.
    - Se o email pertence a um evento: só mostra os cursos DESSE evento.
    - Caso contrário: só mostra os cursos públicos (sem evento nenhum).
    """
    from event_utils import get_event_for_email

    if not current_user.is_admin and email.lower().strip() != current_user.email.lower().strip():
        raise HTTPException(status_code=403, detail="Você não tem acesso aos cursos de outra pessoa.")

    db = SessionLocal()
    event = get_event_for_email(db, email)

    query = db.query(Course).filter(Course.active == True)

    if event:
        courses = query.filter(Course.event_id == event["id"]).all()
    else:
        courses = query.filter(Course.event_id.is_(None)).all()

    result = [
        {
            "id": c.id,
            "title": c.title,
            "course_code": c.course_code,
            "scorm_path": c.scorm_path,
            "active": c.active,
            "event_id": c.event_id,
            "color_primary": c.color_primary
            ,"passing_score": c.passing_score
        }
        for c in courses
    ]

    db.close()
    return {"event": event, "courses": result}


@router.put("/courses/{course_code}")
def update_course(
    course_code: str,
    data: CourseUpdateRequest,
    _: CurrentUser = Depends(require_admin),
):
    db = SessionLocal()

    course = db.query(Course).filter(
        Course.course_code == course_code
    ).first()

    if not course:
        db.close()
        return {"success": False, "message": "Curso não encontrado."}

    if data.title is not None:
        course.title = data.title

    if data.active is not None:
        course.active = data.active

    if data.event_id is not None:
        # manda 0 pra "desvincular do evento" (voltar a ser público)
        course.event_id = None if data.event_id == 0 else data.event_id

    if data.color_primary is not None:
        course.color_primary = data.color_primary

    if data.passing_score is not None:
        if data.passing_score < 0 or data.passing_score > 100:
            db.close()
            return {"success": False, "message": "A nota mínima deve ficar entre 0 e 100."}
        course.passing_score = data.passing_score

    if data.duration_hours is not None and data.duration_hours < 0:
        db.close()
        return {"success": False, "message": "A carga horária não pode ser negativa."}

    if data.catalog_status is not None:
        if data.catalog_status not in CATALOG_STATUSES:
            db.close()
            return {"success": False, "message": "Status de catálogo inválido."}
        course.catalog_status = data.catalog_status

    for field in ("tool", "duration_hours", "catalog_url", "thumbnail_url", "short_description"):
        value = getattr(data, field)
        if value is not None:
            setattr(course, field, value)

    course.updated_at = datetime.utcnow()
    touch_catalog(db)
    db.commit()
    db.refresh(course)
    db.close()

    return {
        "success": True,
        "id": course.id,
        "title": course.title,
        "course_code": course.course_code,
        "scorm_path": course.scorm_path,
        "active": course.active,
        "event_id": course.event_id,
        "color_primary": course.color_primary
        ,"passing_score": course.passing_score,
        "tool": course.tool,
        "duration_hours": course.duration_hours,
        "catalog_url": course.catalog_url,
        "thumbnail_url": course.thumbnail_url,
        "short_description": course.short_description,
        "catalog_status": course.catalog_status,
    }


@router.delete("/courses/{course_code}")
def delete_course(course_code: str, _: CurrentUser = Depends(require_admin)):
    db = SessionLocal()

    course = db.query(Course).filter(
        Course.course_code == course_code
    ).first()

    if not course:
        db.close()
        return {"success": False, "message": "Curso não encontrado."}

    # Limpa matrículas e sessões/progresso ligados a esse curso
    db.query(Enrollment).filter(
        Enrollment.course_code == course_code
    ).delete()

    db.query(CourseSession).filter(
        CourseSession.course_id == course_code
    ).delete()

    db.delete(course)
    touch_catalog(db)
    db.commit()
    db.close()

    # Tenta remover os arquivos do FTP também (não bloqueia a exclusão se falhar)
    ftp_error = None

    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, 21, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)
        remove_dir_ftp(ftp, f"{FTP_BASE_DIR}/{course_code}")
        ftp.quit()
    except Exception as e:
        ftp_error = str(e)

    return {
        "success": True,
        "message": "Curso excluído com sucesso.",
        "ftp_warning": ftp_error
    }
