from datetime import datetime
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile
from database import SessionLocal
from models import Course, Enrollment, CourseSession
from schemas import CourseCreateRequest, CourseUpdateRequest

import os
import zipfile
import ftplib
import tempfile

router = APIRouter()

FTP_HOST = "147.93.37.72"
FTP_USER = "u124251760.lms.iaclube.help"
FTP_PASS = os.getenv("FTP_PASSWORD")
FTP_BASE_DIR = "/public_html/scorm"
PUBLIC_BASE_URL = "https://lms.iaclube.help/scorm"


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
    color_primary: Optional[str] = Form(None)
):
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = os.path.join(tmp_dir, file.filename)

        with open(zip_path, "wb") as buffer:
            buffer.write(await file.read())

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)

        manifest_files = []

        for root, dirs, files in os.walk(tmp_dir):
            for name in files:
                if name == "imsmanifest.xml":
                    manifest_files.append(os.path.join(root, name))

        if len(manifest_files) == 0:
            return {
                "success": False,
                "message": "Arquivo inválido: nenhum imsmanifest.xml encontrado."
            }

        if len(manifest_files) > 1:
            return {
                "success": False,
                "message": "Arquivo inválido: o ZIP contém mais de um pacote SCORM."
            }

        scorm_root = os.path.dirname(manifest_files[0])

        launcher_path = os.path.join(scorm_root, "scormdriver", "indexAPI.html")

        if not os.path.exists(launcher_path):
            return {
                "success": False,
                "message": "Arquivo inválido: scormdriver/indexAPI.html não encontrado."
            }

        # Upload via FTP para a Hostinger
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, 21, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)

        remote_course_dir = f"{FTP_BASE_DIR}/{course_code}"
        upload_dir_ftp(ftp, scorm_root, remote_course_dir)
        ftp.quit()

        scorm_path = f"{PUBLIC_BASE_URL}/{course_code}/scormdriver/indexAPI.html"

        db = SessionLocal()

        course = Course(
            title=title,
            course_code=course_code,
            scorm_path=scorm_path,
            active=True,
            event_id=event_id,
            color_primary=color_primary,
            created_at=datetime.utcnow()
        )

        db.add(course)
        db.commit()
        db.refresh(course)
        db.close()

        return {
            "id": course.id,
            "title": course.title,
            "course_code": course.course_code,
            "scorm_path": course.scorm_path,
            "event_id": course.event_id,
            "color_primary": course.color_primary,
            "message": "Course uploaded successfully"
        }


@router.post("/courses")
def create_course(data: CourseCreateRequest):
    db = SessionLocal()

    course = Course(
        title=data.title,
        course_code=data.course_code,
        scorm_path=data.scorm_path,
        active=True,
        event_id=data.event_id,
        color_primary=data.color_primary,
        created_at=datetime.utcnow()
    )

    db.add(course)
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
    }


@router.get("/courses")
def list_courses():
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
            "created_at": c.created_at
        }
        for c in courses
    ]

    db.close()
    return result


@router.get("/courses/public")
def list_public_courses(email: str):
    """
    Lista usada na aba 'Todos Cursos'.
    - Se o email pertence a um evento: só mostra os cursos DESSE evento.
    - Caso contrário: só mostra os cursos públicos (sem evento nenhum).
    """
    from event_utils import get_event_for_email

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
        }
        for c in courses
    ]

    db.close()
    return {"event": event, "courses": result}


@router.put("/courses/{course_code}")
def update_course(course_code: str, data: CourseUpdateRequest):
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
    }


@router.delete("/courses/{course_code}")
def delete_course(course_code: str):
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
