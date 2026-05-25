from typing import Optional
from pydantic import BaseModel


class SessionStartRequest(BaseModel):
    student_id: str
    course_id: str


class SessionUpdateRequest(BaseModel):
    status: Optional[str] = None
    session_time: Optional[str] = None
    completed: Optional[bool] = None
    suspend_data: Optional[str] = None
    lesson_location: Optional[str] = None


class CourseCreateRequest(BaseModel):
    title: str
    course_code: str
    scorm_path: str


class StudentCreateRequest(BaseModel):
    student_code: str
    name: str
    email: str


class EnrollmentCreateRequest(BaseModel):
    student_code: str
    course_code: str