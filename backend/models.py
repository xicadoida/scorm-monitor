from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database import Base


class CourseSession(Base):
    __tablename__ = "course_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True)
    course_id = Column(String, index=True)

    status = Column(String, default="not_attempted")
    completed = Column(Boolean, default=False)

    session_time = Column(String, default="")
    suspend_data = Column(String, default="")
    lesson_location = Column(String, default="")

    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    course_code = Column(String, unique=True, index=True)
    scorm_path = Column(String)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String, index=True)
    course_code = Column(String, index=True)
    active = Column(Boolean, default=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)