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
    event_id: Optional[int] = None


class StudentCreateRequest(BaseModel):
    student_code: str
    name: str
    email: str


class EnrollmentCreateRequest(BaseModel):
    student_code: str
    course_code: str

class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    active: Optional[bool] = None
    event_id: Optional[int] = None

class ClassCreateRequest(BaseModel):
    name: str


class AddStudentsToClassRequest(BaseModel):
    student_codes: list[str]


class ChangePasswordRequest(BaseModel):
    student_code: str
    current_password: str
    new_password: str


class EventCreateRequest(BaseModel):
    name: str
    logo_url: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None


class EventUpdateRequest(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None


class EventAddEmailsRequest(BaseModel):
    emails: list[str]