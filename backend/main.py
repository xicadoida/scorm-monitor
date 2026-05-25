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

app = FastAPI()
app.include_router(courses_router)
app.include_router(sessions_router)
app.include_router(students_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "SCORM Monitor API running"}
