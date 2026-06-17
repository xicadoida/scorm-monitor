from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database import Base


class CourseSession(Base):
    __tablename__ = "course_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(100), index=True)
    course_id = Column(String(100), index=True)
    status = Column(String(50), default="not_attempted")
    completed = Column(Boolean, default=False)
    session_time = Column(String(50), default="")
    suspend_data = Column(String(5000), default="")
    lesson_location = Column(String(255), default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    course_code = Column(String(100), unique=True, index=True)
    scorm_path = Column(String(500))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), unique=True, index=True)
    name = Column(String(255))
    email = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    password_hash = Column(String(255))


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), index=True)
    course_code = Column(String(100), index=True)
    active = Column(Boolean, default=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)


class ClassGroup(Base):
    __tablename__ = "class_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClassStudent(Base):
    __tablename__ = "class_students"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, index=True)
    student_code = Column(String(100), index=True)