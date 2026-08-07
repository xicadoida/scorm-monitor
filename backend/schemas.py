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
    color_primary: Optional[str] = None


class StudentCreateRequest(BaseModel):
    student_code: str
    name: str
    email: str


class StudentUpdateRequest(BaseModel):
    name: Optional[str] = None


class EnrollmentCreateRequest(BaseModel):
    student_code: str
    course_code: str

class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    active: Optional[bool] = None
    event_id: Optional[int] = None
    color_primary: Optional[str] = None

class ClassCreateRequest(BaseModel):
    name: str


class AddStudentsToClassRequest(BaseModel):
    student_codes: list[str]


class ChangePasswordRequest(BaseModel):
    student_code: str
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    password: str


class EventCreateRequest(BaseModel):
    name: str
    logo_url: Optional[str] = None
    slug: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    item_name: Optional[str] = None
    show_progress: Optional[bool] = True
    show_footer: Optional[bool] = False


class EventUpdateRequest(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    slug: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    item_name: Optional[str] = None
    show_progress: Optional[bool] = None
    show_footer: Optional[bool] = None


class EventAddEmailsRequest(BaseModel):
    emails: list[str]

class AttendanceModuleCreateRequest(BaseModel):
    name: str
    event_id: Optional[int] = None
    position: Optional[int] = 0


class AttendanceModuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    event_id: Optional[int] = None
    position: Optional[int] = None


class AttendanceModulePartCreateRequest(BaseModel):
    course_code: Optional[str] = None
    label: Optional[str] = None
    date: Optional[str] = None
    position: Optional[int] = 0


class AttendanceModulePartUpdateRequest(BaseModel):
    course_code: Optional[str] = None
    label: Optional[str] = None
    date: Optional[str] = None
    position: Optional[int] = None


class AttendanceRecordUpdateRequest(BaseModel):
    status: str
