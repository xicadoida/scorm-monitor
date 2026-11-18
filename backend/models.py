from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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
    # Uma exclusão administrativa arquiva o curso em vez de apagar sessões,
    # matrículas e referências de frequência que usam o course_code.
    archived_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # NULL = curso público (aparece pra todo mundo que não é de evento nenhum)
    # preenchido = curso só aparece pra alunos cujo email está na lista do evento
    event_id = Column(Integer, nullable=True, index=True)
    # Cor usada nos elementos de ação do cartão deste curso.
    color_primary = Column(String(20), nullable=True)
    passing_score = Column(Integer, default=80)
    # Metadados usados pelo catálogo público. São opcionais para preservar os
    # cursos existentes, que podem ser enriquecidos aos poucos pelo admin.
    tool = Column(String(255), nullable=True)
    duration_hours = Column(Integer, nullable=True)
    catalog_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    short_description = Column(String(500), nullable=True)
    catalog_status = Column(String(30), default="active")
    updated_at = Column(DateTime, default=datetime.utcnow)


class CatalogState(Base):
    """Registro único com a versão atual do catálogo público."""
    __tablename__ = "catalog_state"

    id = Column(Integer, primary_key=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ScormPublication(Base):
    """Intenção durável e exclusão por curso; committed acompanha Course no commit."""
    __tablename__ = 'scorm_publications'

    course_code = Column(String(100), primary_key=True)
    token = Column(String(32), nullable=False)
    state = Column(String(20), nullable=False, default='pending')
    target_key = Column(String(64), nullable=False)
    had_previous = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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
    # Eventos arquivados continuam existindo para manter o contexto histórico
    # de cursos, perfis, presenças e auditoria, mas não aceitam acesso.
    active = Column(Boolean, default=True, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventEmail(Base):
    __tablename__ = "event_emails"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, index=True)
    email = Column(String(255), index=True)
    # Convites removidos são revogados para preservar a trilha do vínculo
    # sem continuarem elegíveis para o evento.
    active = Column(Boolean, default=True, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), unique=True, index=True)
    name = Column(String(255))
    email = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # O código permanece reservado após a desativação. Isso preserva o
    # histórico e impede que uma nova pessoa herde registros antigos.
    active = Column(Boolean, default=True, nullable=False, index=True)
    deactivated_at = Column(DateTime, nullable=True, index=True)
    password_hash = Column(String(255))
    # Incrementado ao trocar senha para invalidar tokens de sessões antigas.
    auth_token_version = Column(Integer, default=0, nullable=False)
    # NULL significa que a posse do endereço ainda não foi comprovada. A
    # migração deliberadamente não preenche esse campo para contas antigas.
    email_verified_at = Column(DateTime, nullable=True, index=True)
    __table_args__ = (
        # Login e verificacao normalizam espacos e maiusculas. O indice impede
        # que duas contas virem o mesmo endereco logico em uma corrida.
        Index("uq_students_email_normalized", func.lower(func.trim(email)), unique=True),
    )


class RegistrationProfile(Base):
    """Dados de inscrição da pessoa, separados de matrículas em cursos."""
    __tablename__ = "registration_profiles"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), unique=True, index=True, nullable=False)
    # pf | pj | not_informed (contas criadas antes desta funcionalidade)
    person_type = Column(String(20), default="not_informed", nullable=False, index=True)
    accepted_terms_at = Column(DateTime, nullable=True)
    accepted_terms_url = Column(String(500), nullable=True)
    event_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AccessEvent(Base):
    """Auditoria sem IP real: apenas identificador HMAC não reversível."""
    __tablename__ = "access_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    success = Column(Boolean, default=True, nullable=False, index=True)
    student_code = Column(String(100), nullable=True, index=True)
    event_id = Column(Integer, nullable=True, index=True)
    ip_hash = Column(String(64), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    route = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class PasswordResetToken(Base):
    """Token de recupera\u00e7\u00e3o salvo apenas como hash, nunca em texto puro."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class EmailVerificationToken(Base):
    """Token de confirmação salvo apenas como hash, nunca em texto puro.

    ``purpose`` separa confirmação de cadastro, acesso a evento e troca de
    e-mail. O token bruto é enviado somente ao endereço informado e não é
    persistido nem devolvido por esta tabela.
    """
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    event_id = Column(Integer, nullable=True, index=True)
    purpose = Column(String(50), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True, index=True)
    # Contador persistido para que tentativas contra um token válido possam
    # ser bloqueadas sem manter o token em texto puro.
    failed_attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class EventMembership(Base):
    """Vínculo confirmado de uma conta a um evento específico.

    ``EventEmail`` continua sendo uma lista de convidados. Ela não concede
    acesso por si só: apenas uma associação com status ``confirmed`` deve ser
    aceita pelas rotas protegidas.
    """
    __tablename__ = "event_memberships"
    __table_args__ = (
        UniqueConstraint(
            "student_code",
            "event_id",
            name="uq_event_memberships_student_event",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), nullable=False, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    # Endereço comprovado ao criar/reativar este vínculo. Ele permite
    # invalidar imediatamente a associação quando a conta troca de e-mail.
    email = Column(String(255), nullable=False, index=True)
    # pending | confirmed | revoked. O padrão falha fechado: pendente não
    # concede acesso até a confirmação explícita.
    status = Column(String(20), default="pending", nullable=False, index=True)
    confirmed_at = Column(DateTime, nullable=True, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


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
    active = Column(Boolean, default=True, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AttendanceModulePart(Base):
    __tablename__ = "attendance_module_parts"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, index=True)
    course_code = Column(String(100), nullable=True)
    label = Column(String(255), nullable=True)
    date = Column(Date, nullable=True)
    position = Column(Integer, default=0)
    active = Column(Boolean, default=True, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True, index=True)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(100), index=True)
    part_id = Column(Integer, index=True)
    # presente | falta | justificada | a_realizar
    status = Column(String(20), default="a_realizar")
    updated_at = Column(DateTime, default=datetime.utcnow)
