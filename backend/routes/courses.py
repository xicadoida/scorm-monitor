from datetime import datetime
from fastapi import APIRouter

from database import SessionLocal
from models import Course
from schemas import CourseCreateRequest

import os
import zipfile
from fastapi import File, Form, UploadFile

router = APIRouter()


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

@router.post("/courses/upload")
async def upload_course(
    title: str = Form(...),
    course_code: str = Form(...),
    file: UploadFile = File(...)
):
    upload_dir = f"../public/scorm/{course_code}"
    os.makedirs(upload_dir, exist_ok=True)

    zip_path = os.path.join(upload_dir, file.filename)

    with open(zip_path, "wb") as buffer:
        buffer.write(await file.read())

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(upload_dir)

    manifest_files = []

    for root, dirs, files in os.walk(upload_dir):
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
            "message": "Arquivo inválido: o ZIP contém mais de um pacote SCORM. Envie apenas um curso por vez."
        }
    
    scorm_root = os.path.dirname(manifest_files[0])

    launcher_path = os.path.join(scorm_root, "scormdriver", "indexAPI.html")

    if not os.path.exists(launcher_path):
        return {
            "success": False,
            "message": "Arquivo inválido: scormdriver/indexAPI.html não encontrado."
        }

    relative_root = os.path.relpath(scorm_root, "../public/scorm").replace("\\", "/")

    scorm_path = f"/scorm/{relative_root}/scormdriver/indexAPI.html"

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
