from datetime import datetime
from fastapi import APIRouter, File, Form, UploadFile
from database import SessionLocal
from models import Course
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
    file: UploadFile = File(...)
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
        ftp.connect(FTP_HOST, 21)
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
        "active": course.active
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
            "created_at": c.created_at
        }
        for c in courses
    ]

    db.close()
    return result


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

    db.commit()
    db.refresh(course)
    db.close()

    return {
        "success": True,
        "id": course.id,
        "title": course.title,
        "course_code": course.course_code,
        "scorm_path": course.scorm_path,
        "active": course.active
    }