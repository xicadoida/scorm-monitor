from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from database import SessionLocal
from models import Course, Enrollment, CourseSession, ScormPublication
from schemas import CourseCreateRequest, CourseUpdateRequest
from catalog_utils import touch_catalog
from auth_utils import CurrentUser, get_current_user, require_admin

import os
from scorm_package import InvalidPackage, prepare_package, validate_course_code
import ftplib
import tempfile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from scorm_publication import PublicationError, PublicationBusy, RecoveryRequired, publish_course

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


def upload_dir_ftp(ftp, local_dir, remote_dir):
    try:
        ftp.mkd(remote_dir)
    except ftplib.error_perm:
        pass

    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"

        if os.path.isdir(local_path):
            upload_dir_ftp(ftp, local_path, remote_path)
        else:
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)


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
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            validate_course_code(course_code)
            scorm_root = await prepare_package(file, tmp_dir)
            result = await run_in_threadpool(publish_course, scorm_root, course_code, metadata={
                "title": title, "event_id": event_id, "color_primary": color_primary,
                "passing_score": passing_score or 80, "tool": tool,
                "duration_hours": duration_hours, "catalog_url": catalog_url,
                "thumbnail_url": thumbnail_url, "short_description": short_description,
                "catalog_status": catalog_status,
            })
        except InvalidPackage as error:
            return {"success": False, "message": str(error)}
        except PublicationBusy as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (RecoveryRequired, SQLAlchemyError) as error:
            raise HTTPException(status_code=503, detail="Publicação indisponível ou pendente de reconciliação. Consulte o journal SCORM.") from error
        except PublicationError as error:
            return {"success": False, "message": str(error)}
    return dict(result, message="Course uploaded successfully")


@router.post("/courses/{course_code}/replace-file")
async def replace_course_file(
    course_code: str,
    file: UploadFile = File(...),
    _: CurrentUser = Depends(require_admin),
):
    """Valida e publica com staging/journal, preservando os vínculos do curso."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            validate_course_code(course_code)
            scorm_root = await prepare_package(file, tmp_dir)
            result = await run_in_threadpool(publish_course, scorm_root, course_code)
        except InvalidPackage as error:
            return {"success": False, "message": str(error)}
        except PublicationBusy as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (RecoveryRequired, SQLAlchemyError) as error:
            raise HTTPException(status_code=503, detail="Substituição pendente de reconciliação. Consulte o journal SCORM.") from error
        except PublicationError as error:
            return {"success": False, "message": str(error)}
    return {"success": True, "recovery_pending": result["recovery_pending"],
            "message": "Arquivo SCORM substituído. Progresso, conclusões e presenças foram preservados."}


@router.post("/courses")
def create_course(data: CourseCreateRequest, _: CurrentUser = Depends(require_admin)):
    if data.catalog_status not in CATALOG_STATUSES:
        return {"success": False, "message": "Status de catálogo inválido."}

    db = SessionLocal()
    if db.get(ScormPublication, data.course_code) is not None:
        db.close()
        raise HTTPException(status_code=409, detail="Curso possui publicação pendente.")

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
    if db.get(ScormPublication, course_code) is not None:
        db.close()
        raise HTTPException(status_code=409, detail="Curso possui publicação pendente.")

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
    if db.get(ScormPublication, course_code) is not None:
        db.close()
        raise HTTPException(status_code=409, detail="Curso possui publicação pendente.")

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
