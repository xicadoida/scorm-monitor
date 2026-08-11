from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date
from database import Base


class CourseSession(Base):
    __tablename__ = "course_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(100), index=True)
    course_id = Column(String(100), index=True)
    status = Column(String(50), default="not_attempted")
    completed = Column(Boolean, default=False)
    session_time = Column(String(50), default="")
    score_raw = Column(Integer, nullable=True)
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
    # NULL = curso público (aparece pra todo mundo que não é de evento nenhum)
    # preenchido = curso só aparece pra alunos cujo email está na lista do evento
    event_id = Column(Integer, nullable=True, index=True)
    # Cor usada nos elementos de ação do cartão deste curso.
    color_primary = Column(String(20), nullable=True)
    passing_score = Column(Integer, default=80)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    logo_url = Column(String(500), nullable=True)
    slug = Column(String(100), unique=True, nullable=True, index=True)
    color_primary = Column(String(20), nullable=True)
    color_secondary = Column(String(20), nullable=True)
    # nome usado no lugar de "Curso" nos textos da plataforma (ex: "Módulo")
    item_name = Column(String(50), nullable=True)
    show_progress = Column(Boolean, default=True)
    show_footer = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventEmail(Base):
    __tablename__ = "event_emails"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, index=True)
    email = Column(String(255), index=True)
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

class AttendanceModule(Base):
    __tablename__ = "attendance_modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    event_id = Column(Integer, nullable=True, index=True)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AttendanceModulePart(Base):
    __tablename__ = "attendance_module_parts"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, index=True)
    course_code = Column(String(100), nullable=True)
    label = Column(String(255), nullable=True)
    date = Column(Date, nullable=True)
    position = Column(Integer, default=0)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), index=True)
    part_id = Column(Integer, index=True)
    # presente | falta | justificada | a_realizar
    status = Column(String(20), default="a_realizar")
    updated_at = Column(DateTime, default=datetime.utcnow)
