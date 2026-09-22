import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base, SessionLocal

from models import *
from schemas import *

from routes.courses import router as courses_router
from routes.sessions import router as sessions_router
from routes.students import router as students_router
from routes.enrollments import router as enrollments_router
from routes.classes import router as classes_router
from routes.auth import router as auth_router
from routes.events import router as events_router
from routes.attendance import router as attendance_router
from routes.catalog import router as catalog_router
from routes.insights import router as insights_router


app = FastAPI()

app.include_router(courses_router)
app.include_router(sessions_router)
app.include_router(students_router)
app.include_router(enrollments_router)
app.include_router(auth_router)
app.include_router(classes_router)
app.include_router(events_router)
app.include_router(attendance_router)
app.include_router(catalog_router)
app.include_router(insights_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://lms.iaclube.help",
        "https://iaclube.help",
        "https://www.iaclube.help",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Em produ\u00e7\u00e3o o Gunicorn inicia v\u00e1rios workers ao mesmo tempo. Criar
# tabelas aqui permite que dois workers tentem criar a mesma tabela no SQLite,
# derrubando toda a API. O schema deve ser criado pelas migra\u00e7\u00f5es executadas
# antes do restart; esta op\u00e7\u00e3o fica dispon\u00edvel somente para desenvolvimento.
if os.getenv("AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes", "sim"}:
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "SCORM Monitor API running"}
