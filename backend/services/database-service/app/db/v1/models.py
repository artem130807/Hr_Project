from datetime import date, time, datetime, timedelta
from enum import Enum as PyEnum
from typing import Annotated, Optional
import secrets

from sqlalchemy import (
    Integer, String, ARRAY, Float, Boolean, Text, Date, Time, DateTime, Enum, ForeignKey, func,
    UniqueConstraint, CheckConstraint, Index, LargeBinary, JSON, text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import mapped_column, Mapped, DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.types import TypeDecorator

from app.db.v1.enums import (
    BotRoles, CandidateStatus,
    Gender, WorkExpirience, WorkFormat, UpdateDate,
    TestType, MaritalStatus, TestResultsType, Departments,
    CandidateStage, ResumeSearchStatus, HiringRequestStatus, EvaluationStatus,
    CallConversationStatus, VnrHireStatus,
)
from app.db.database import (
    int_pk, str_list, str_uniq, 
    Base, TimestampMixin
)


class PgEnumLabel(TypeDecorator):
    """Bind Python Enum to PostgreSQL ENUM labels.

    - ``by_value=True``  → store ``member.value`` (candidatestatus: Russian labels)
    - ``by_value=False`` → store ``member.name``  (candidatestage: English labels)

    Prod DB is split: statuses were migrated to Russian values; stages still use
    SQLAlchemy default names (employment, archieved, …).
    """

    cache_ok = True
    impl = String

    def __init__(
        self,
        enum_cls: type[PyEnum],
        *,
        name: str | None = None,
        by_value: bool = True,
    ):
        self.enum_cls = enum_cls
        self.by_value = by_value
        type_name = name or enum_cls.__name__.lower()
        labels = [member.value if by_value else member.name for member in enum_cls]
        self._pg = PG_ENUM(*labels, name=type_name, create_type=False)
        super().__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return self._pg
        return dialect.type_descriptor(String(64))

    def _to_label(self, value):
        if isinstance(value, self.enum_cls):
            return value.value if self.by_value else value.name
        if isinstance(value, PyEnum):
            return value.value if self.by_value else value.name
        if isinstance(value, str):
            # Prefer member name lookup, then value lookup
            try:
                member = self.enum_cls[value]
            except KeyError:
                try:
                    member = self.enum_cls(value)
                except ValueError:
                    return value
            return member.value if self.by_value else member.name
        return str(value)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self._to_label(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # Prod may store member names or Russian values depending on when the
        # PostgreSQL enum was created. Accept both.
        try:
            return self.enum_cls[value]
        except KeyError:
            try:
                return self.enum_cls(value)
            except ValueError as exc:
                raise LookupError(
                    f"Unknown {self.enum_cls.__name__} label {value!r}"
                ) from exc

    @property
    def enums(self):
        return list(self._pg.enums)


def _pg_enum(enum_cls, *, by_value: bool = True):
    return PgEnumLabel(enum_cls, by_value=by_value)


class CompanyCandidateImage(Base, TimestampMixin):
    __tablename__ = 'company_candidate_images'

    id: Mapped[int_pk]

    soft_skills: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    red_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    common_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DepartmentCandidateImage(Base, TimestampMixin):
    __tablename__ = 'department_candidate_images'

    id: Mapped[int_pk]
    hard_skills: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expirience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    common_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)


class ServiceClient(Base, TimestampMixin):
    __tablename__ = "service_clients"

    id: Mapped[int_pk]
    client_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class HrNegotiationFlag(Base, TimestampMixin):
    """Per-ERP-user flag: responsible for HH negotiations processing."""
    __tablename__ = "hr_negotiation_flags"

    erp_user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    negotations_processing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BotUser(Base, TimestampMixin):
    __tablename__ = "bot_users"
    id: Mapped[int_pk]
    
    telegram_id: Mapped[str_uniq]
    name: Mapped[str_uniq]
    role: Mapped[str] = mapped_column(Enum(BotRoles), nullable=False)

    candidate_profile: Mapped["Candidate"] = relationship(
        "Candidate", back_populates="bot_user", uselist=False
        )
    employee_profile: Mapped["Employee"] = relationship(
        "Employee", back_populates="bot_user", uselist=False
        )
    progress: Mapped["BotUserProgress"] = relationship(
        "BotUserProgress", back_populates="bot_user", uselist=False, lazy="joined", cascade="all, delete-orphan"
    )


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"
    
    id: Mapped[int_pk]
    # Nullable: HH-imported hires may have no Telegram bot_user yet
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bot_users.id"), unique=True, nullable=True)
    erp_user_id: Mapped[Optional[str]] = mapped_column(String(36), unique=True, nullable=True, index=True)
    candidate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String)
    gender: Mapped[Optional[str]] = mapped_column(Enum(Gender), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department: Mapped[str] = mapped_column(String)
    position: Mapped[str] = mapped_column(String)
    marital_status: Mapped[Optional[str]] = mapped_column(Enum(MaritalStatus), nullable=True)
    hobbies: Mapped[Optional[str_list]] = mapped_column(nullable=True)
    personal_characteristics: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    service_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    date_hired: Mapped[date] = mapped_column(Date)
    date_fired: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    
    # Связь с кандидатом
    bot_user: Mapped["BotUser"] = relationship(
        "BotUser", back_populates="employee_profile"
        )
    candidate: Mapped[Optional["Candidate"]] = relationship(
        back_populates="employee"
        )
    vnr_hire: Mapped[Optional["VnrHire"]] = relationship(
        "VnrHire", back_populates="employee", uselist=False
    )
    children: Mapped[list["Child"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
        )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
        )
    adaptation_enrollments: Mapped[list["AdaptationEnrollment"]] = relationship(
        "AdaptationEnrollment",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="AdaptationEnrollment.start_date.desc()",
    )
    contact_points: Mapped[list["ContactPoint"]] = relationship(
        "ContactPoint", back_populates="employee", cascade="all, delete-orphan"
    )


class OrganizationDepartment(Base, TimestampMixin):
    """Organizational unit; separate from the recruiting candidate profile."""

    __tablename__ = "organization_departments"

    id: Mapped[int_pk]
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    lead_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    lead_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    contact_points: Mapped[list["ContactPoint"]] = relationship(
        "ContactPoint", back_populates="department", cascade="all, delete-orphan"
    )


class ContactPoint(Base, TimestampMixin):
    """A normalized employee or shared department contact."""

    __tablename__ = "contact_points"
    __table_args__ = (
        CheckConstraint("contact_type IN ('telegram','phone','email')", name="ck_contact_type"),
        CheckConstraint("usage_type IN ('personal','work_personal','shared')", name="ck_contact_usage_type"),
        CheckConstraint("owner_type IN ('employee','department')", name="ck_contact_owner_type"),
        CheckConstraint(
            "(owner_type='employee' AND employee_id IS NOT NULL AND department_id IS NULL) OR "
            "(owner_type='department' AND department_id IS NOT NULL AND employee_id IS NULL)",
            name="ck_contact_one_owner",
        ),
        CheckConstraint("owner_type <> 'department' OR usage_type='shared'", name="ck_department_contact_shared"),
        CheckConstraint("NOT is_primary OR owner_type='employee'", name="ck_contact_primary_employee"),
        CheckConstraint(
            "NOT allow_adaptation OR (owner_type='employee' AND contact_type='telegram' AND usage_type <> 'shared')",
            name="ck_contact_adaptation_target",
        ),
        Index("ix_contact_lookup", "contact_type", "normalized_value"),
        Index("ix_contact_employee_active", "employee_id", "is_active"),
        Index("ix_contact_department_active", "department_id", "is_active"),
        Index(
            "uq_contact_personal_active", "contact_type", "normalized_value", unique=True,
            postgresql_where=text("is_active = true AND usage_type <> 'shared'"),
            sqlite_where=text("is_active = 1 AND usage_type <> 'shared'"),
        ),
        Index(
            "uq_contact_department_active_value", "department_id", "contact_type", "normalized_value", unique=True,
            postgresql_where=text("is_active = true AND owner_type = 'department'"),
            sqlite_where=text("is_active = 1 AND owner_type = 'department'"),
        ),
        Index(
            "uq_contact_employee_primary", "employee_id", "contact_type", "usage_type", unique=True,
            postgresql_where=text("employee_id IS NOT NULL AND is_primary = true AND is_active = true"),
            sqlite_where=text("employee_id IS NOT NULL AND is_primary = 1 AND is_active = 1"),
        ),
    )

    id: Mapped[int_pk]
    contact_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(320), nullable=False)
    usage_type: Mapped[str] = mapped_column(String(24), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(24), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organization_departments.id"), nullable=True, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_adaptation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    employee: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="contact_points")
    department: Mapped[Optional["OrganizationDepartment"]] = relationship("OrganizationDepartment", back_populates="contact_points")


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"
    id: Mapped[int_pk]
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # личные данные
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bot_users.id"), unique=True, nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    marital_status: Mapped[Optional[MaritalStatus]] = mapped_column(Enum(MaritalStatus), nullable=True)
    hobbies: Mapped[Optional[str_list]] = mapped_column(nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[Gender]] = mapped_column(Enum(Gender), nullable=True)
    personal_characteristics: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    children: Mapped[list["Child"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")

    hh_resume_link: Mapped[str] = mapped_column(String, nullable=False)

    # общие данные
    languages: Mapped[Optional[str_list]] = mapped_column(nullable=True)
    relevant_position_expirience: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    certain_position_expirience: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    total_work_expirience: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    other_work_expirience: Mapped[Optional[str_list]] = mapped_column(nullable=True)
    average_service_length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    education: Mapped[Optional[str_list]] = mapped_column(nullable=True)
    hard_skills: Mapped[Optional[str_list]] = mapped_column(nullable=True)
    work_programs: Mapped[Optional[str_list]] = mapped_column(nullable=True)
    resume_update_date: Mapped[Optional[UpdateDate]] = mapped_column(Enum(UpdateDate), nullable=True)
    active_search: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    salary_expectations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hr_comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_contact_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_contact_owner_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    next_contact_owner_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    stage: Mapped[CandidateStage] = mapped_column(
        _pg_enum(CandidateStage, by_value=False),
        nullable=False,
    )
    
    vacancies: Mapped[list["CandidateVacancyRelation"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    test_results: Mapped[list["CandidateTestResult"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    bot_user: Mapped["BotUser"] = relationship(
        "BotUser", back_populates="candidate_profile"
        )
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="candidate"
    )
    vnr_hire: Mapped[Optional["VnrHire"]] = relationship(
        "VnrHire", back_populates="candidate", uselist=False
    )
    question_answers: Mapped[list["CandidateQuestionAnswer"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    negotiations: Mapped[list["Negotiation"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    appointment: Mapped[Optional["HrAvailability"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    ai_evaluations: Mapped[list["CandidateAiEvaluation"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    documents: Mapped[Optional["CandidateDocs"]] = relationship(
        "CandidateDocs", back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    document_invites: Mapped[list["CandidateDocumentInvite"]] = relationship(
        "CandidateDocumentInvite", back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateDocumentInvite(Base, TimestampMixin):
    __tablename__ = "candidate_document_invites"

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="document_invites")


class CandidateDocs(Base, TimestampMixin):
    __tablename__ = "candidate_docs"
    __table_args__ = (
        CheckConstraint("status IN ('submitted', 'complete')", name="ck_candidate_docs_status"),
    )

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    s3_prefix: Mapped[str] = mapped_column(String(500), nullable=False)
    manifest: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted", index=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="documents")


class CandidateDocumentUploadSession(Base, TimestampMixin):
    """Server-side draft; the browser retains only the unguessable token."""

    __tablename__ = "candidate_document_upload_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'submitted', 'expired')", name="ck_candidate_document_upload_session_status"),
    )

    id: Mapped[int_pk]
    session_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    invite_id: Mapped[int] = mapped_column(ForeignKey("candidate_document_invites.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    files: Mapped[list["CandidateDocumentUploadFile"]] = relationship(
        "CandidateDocumentUploadFile", back_populates="session", cascade="all, delete-orphan"
    )


class CandidateDocumentUploadFile(Base, TimestampMixin):
    __tablename__ = "candidate_document_upload_files"
    __table_args__ = (
        CheckConstraint("status IN ('uploaded', 'submitted')", name="ck_candidate_document_upload_file_status"),
    )

    id: Mapped[int_pk]
    file_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_document_upload_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    s3_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploaded", index=True)
    session: Mapped["CandidateDocumentUploadSession"] = relationship(
        "CandidateDocumentUploadSession", back_populates="files"
    )


class Child(Base, TimestampMixin):
    __tablename__ = "children"
    id: Mapped[int_pk]

    # Связь с кандидатом
    candidate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    # Связь с сотрудником
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)

    full_name: Mapped[str] = mapped_column(String, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date)

    # Обратная связь
    candidate: Mapped["Candidate"] = relationship(back_populates="children")
    employee: Mapped["Employee"] = relationship(back_populates="children") 


class CompanyContact(Base, TimestampMixin):
    __tablename__ = "company_contacts"

    id: Mapped[int_pk]
    hr_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone_number: Mapped[str_list]


class Vacancy(Base, TimestampMixin):
    __tablename__ = "vacancies"
    id: Mapped[int_pk]
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    vacancy_type_id: Mapped[str] = mapped_column(String, nullable=False)
    billing_type_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    professional_roles_id: Mapped[str_list]
    hh_vacancy_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hh_vacancy_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    synonyms: Mapped[Optional[str_list]]
    department: Mapped[str] = mapped_column(Enum(Departments), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    area_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    schedule_id: Mapped[str] = mapped_column(String, nullable=True)
    employment_id: Mapped[str] = mapped_column(String, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(Enum(Gender), nullable=True)
    languages: Mapped[Optional[str_list]]
    personal_characteristics: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    relevant_position_expirience: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    certain_position_expirience: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    total_work_expirience: Mapped[Optional[str]] = mapped_column(Enum(WorkExpirience), nullable=True)
    other_work_expirience: Mapped[Optional[str_list]]
    average_service_length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    education: Mapped[Optional[str_list]]
    required_hard_skills: Mapped[Optional[str_list]]
    optional_hard_skills: Mapped[Optional[str_list]]
    main_tasks: Mapped[Optional[str_list]]
    secondary_tasks: Mapped[Optional[str_list]]
    work_programs: Mapped[Optional[str_list]]
    kpi_metrics: Mapped[Optional[str_list]]
    resume_update_date: Mapped[Optional[str]] = mapped_column(Enum(UpdateDate))
    active_search: Mapped[Optional[bool]] = mapped_column(Boolean)
    salary_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gross: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    work_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_internal_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # TZ: planned close + template + link to hiring request
    planned_close_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    hiring_request_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employee_requests.id"), nullable=True
    )
    # Shared candidate filter (many vacancies → one filter; vacancy → one filter)
    filter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vacancy_filters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    negotiations: Mapped[list["Negotiation"]] = relationship(
        back_populates='vacancy', cascade="all, delete-orphan"
    )
    candidates: Mapped[list["CandidateVacancyRelation"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )
    test_relation: Mapped[list["VacancyTestRelation"]] = relationship(
        back_populates="vacancy"
    )
    filter: Mapped[Optional["VacancyFilter"]] = relationship(
        back_populates="vacancies",
    )


class VacancyFilter(Base, TimestampMixin):
    """
    Reusable vacancy candidate filter.
    One filter may be linked to many vacancies; a vacancy has at most one filter.
    """
    __tablename__ = "vacancy_filters"

    id: Mapped[int_pk]
    city: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    age_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    age_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    experience: Mapped[Optional[str]] = mapped_column(Enum(WorkExpirience), nullable=True)
    work_format: Mapped[Optional[str]] = mapped_column(Enum(WorkFormat), nullable=True)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="discard", server_default="discard"
    )

    vacancies: Mapped[list["Vacancy"]] = relationship(
        back_populates="filter",
    )


class CandidateVacancyRelation(Base, TimestampMixin):
    __tablename__ = "candidate_vacancy_relations"
    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), nullable=False)
    status: Mapped[str] = mapped_column(_pg_enum(CandidateStatus), nullable=False)
    status_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tests_not_completed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    perfect_candidate: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    candidate: Mapped["Candidate"] = relationship(back_populates="vacancies", lazy="joined")
    vacancy: Mapped["Vacancy"] = relationship(back_populates="candidates", lazy="joined")


class VnrHire(Base, TimestampMixin):
    """Candidate hired (ВНР) and attributed to the HR user who set the status.

    HR users live in ERP (erp_user_id / X-Actor-Id), not a local users table.
    ``hr_user_id`` is that UUID so profile stats can be scoped per recruiter.
    """

    __tablename__ = "vnr_hires"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_vnr_hires_candidate_id"),
        Index("ix_vnr_hires_hr_user_id", "hr_user_id"),
        Index("ix_vnr_hires_hr_status", "hr_user_id", "status"),
    )

    id: Mapped[int_pk]
    hr_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    hr_user_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    vacancy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vacancies.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VnrHireStatus.in_work.value, index=True
    )

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="vnr_hire")
    employee: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="vnr_hire")
    vacancy: Mapped[Optional["Vacancy"]] = relationship("Vacancy")


class Test(Base, TimestampMixin):
    __tablename__ = "tests"

    id: Mapped[int_pk]
    name: Mapped[str] = mapped_column(String, nullable=False)
    test_type: Mapped[str] = mapped_column(Enum(TestType), nullable=False)
    results_type: Mapped[str] = mapped_column(Enum(TestResultsType), nullable=False)

    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test", cascade="all, delete-orphan"
    )

    instruction_text: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Professional Q&A public take: optional time limit (minutes)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # связь с результатами
    results: Mapped[list["CandidateTestResult"]] = relationship(
        back_populates="test",
        cascade="all, delete-orphan"
    )
    vacancy_relation: Mapped[list["VacancyTestRelation"]] = relationship(back_populates="test")


class TestQuestion(Base, TimestampMixin):
    __tablename__ = "test_questions"
    id: Mapped[int_pk]

    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)   # сам вопрос
    # Professional MCQ options (JSON list of strings); empty/null → free-text
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    correct_option_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    test: Mapped["Test"] = relationship(back_populates="questions")
    answers: Mapped[list["CandidateQuestionAnswer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class CandidateTestResult(Base, TimestampMixin):
    __tablename__ = "candidate_test_results"
    __table_args__ = (
        UniqueConstraint("candidate_id", "test_id", name="uq_candidate_test"),
    )
    id: Mapped[int_pk]

    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"))

    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    image_content_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    has_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # связи ORM
    candidate: Mapped["Candidate"] = relationship(back_populates="test_results")
    test: Mapped["Test"] = relationship(back_populates="results")
    answers: Mapped[list["CandidateQuestionAnswer"]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )


class CandidateQuestionAnswer(Base, TimestampMixin):
    __tablename__ = "candidate_question_answers"
    __table_args__ = (
        UniqueConstraint("candidate_id", "question_id", name="uq_candidate_question"),
    )

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("test_questions.id"), nullable=False)
    result_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("candidate_test_results.id", ondelete="SET NULL"),
        nullable=True,
    )

    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="question_answers")
    question: Mapped["TestQuestion"] = relationship(back_populates="answers")
    result: Mapped[Optional["CandidateTestResult"]] = relationship(back_populates="answers")


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"
    
    id: Mapped[int_pk]
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), nullable=False)
    approver_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approver_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)

    new_status: Mapped[str] = mapped_column(String(200), nullable=False)
    comments: Mapped[str] = mapped_column(String)
    
    vacancy: Mapped["Vacancy"] = relationship(back_populates="approvals")
    candidate: Mapped["Candidate"] = relationship(back_populates="approvals")


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    
    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=True)
    
    review_text: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer)  # Например, от 1 до 5
    
    # Связь с кандидатами и сотрудниками
    candidate: Mapped["Candidate"] = relationship(back_populates="reviews")
    employee: Mapped["Employee"] = relationship(back_populates="reviews")


class Token(Base, TimestampMixin):
    __tablename__ = 'tokens'

    id: Mapped[int_pk]
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    role: Mapped[str] = mapped_column(Enum(BotRoles), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64))

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @staticmethod
    def generate(role: BotRoles, entity_id: int | str | None = None, ttl_minutes: int = 20160):
        return Token(
            token=secrets.token_urlsafe(16), 
            role=role,
            entity_id=str(entity_id) if entity_id is not None else "0",
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes)
        )


class BotUserProgress(Base, TimestampMixin):
    __tablename__ = 'candidates_progress'

    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.id"), nullable=False)

    vacancy_description: Mapped[bool] = mapped_column(Boolean, default=False)
    company_info: Mapped[bool] = mapped_column(Boolean, default=False)
    corp_culture: Mapped[bool] = mapped_column(Boolean, default=False)
    my_resume: Mapped[bool] = mapped_column(Boolean, default=False)
    agreement: Mapped[bool] = mapped_column(Boolean, default=False)
    test_disc: Mapped[bool] = mapped_column(Boolean, default=False)
    test_adizes: Mapped[bool] = mapped_column(Boolean, default=False)

    bot_user: Mapped["BotUser"] = relationship("BotUser", back_populates="progress", uselist=False)


class VacancyTestRelation(Base, TimestampMixin):
    __tablename__ = 'vacancy_test_relations'

    id: Mapped[int_pk]
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), nullable=False)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"))

    vacancy: Mapped["Vacancy"] = relationship(back_populates="test_relation")
    test: Mapped["Test"] = relationship(back_populates="vacancy_relation")
 


class HrAvailability(Base, TimestampMixin):
    __tablename__ = "hr_availability"

    id: Mapped[int_pk]
    hr_id: Mapped[str] = mapped_column(String(36), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False)
    candidate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("candidates.id"), nullable=True)

    candidate: Mapped[Optional["Candidate"]] = relationship(back_populates="appointment")


class Negotiation(Base, TimestampMixin):
    __tablename__ = 'negotiations'

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey('vacancies.id'), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False)

    candidate: Mapped["Candidate"] = relationship(back_populates="negotiations")
    vacancy: Mapped["Vacancy"] = relationship(back_populates='negotiations')


class AutoSearch(Base, TimestampMixin):
    __tablename__ = 'auto_search'

    id: Mapped[int_pk]
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_today: Mapped[int] = mapped_column(Integer, nullable=False)
    total_sent: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    invite_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)  # Количество приглашений для отправки


class ReviewedResume(Base, TimestampMixin):
    __tablename__ = 'reviewed_resumes'

    id: Mapped[int_pk]
    resume_id: Mapped[str] = mapped_column(String, nullable=False)
    auto_search_id: Mapped[int] = mapped_column(ForeignKey('auto_search.id'), nullable=False)
    status: Mapped[ResumeSearchStatus] = mapped_column(Enum(ResumeSearchStatus), nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Оценка от AI (0-100)
    evaluation_status: Mapped[EvaluationStatus] = mapped_column(Enum(EvaluationStatus), nullable=False, default=EvaluationStatus.pending)


class EmployeeRequest(Base, TimestampMixin):
    __tablename__ = "employee_requests"
    id: Mapped[int_pk]

    # General Info
    position: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[Departments] = mapped_column(Enum(Departments), nullable=False)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    urgency: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Contact Info
    manager_name: Mapped[str] = mapped_column(String, nullable=False)
    manager_position: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    backup_contact: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Opening Reason
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    previous_employee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    probation_period: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Job Description
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reporting: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    horizontal_connections: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    growth_prospects: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tasks
    daily_tasks: Mapped[Optional[str_list]] 
    weekly_tasks: Mapped[Optional[str_list]]
    project_tasks: Mapped[Optional[str_list]] 

    # KPI
    kpi_metrics: Mapped[Optional[str_list]] 
    expected_results_probation: Mapped[Optional[str_list]] 
    priorities_3months: Mapped[Optional[str_list]] 

    # Requirements
    mandatory_requirements: Mapped[str_list] 
    desired_requirements: Mapped[Optional[str_list]] 
    age_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    age_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    total_experience_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    relevant_experience_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Hard/Soft Skills
    required_hard_skills: Mapped[Optional[str_list]] 
    optional_hard_skills: Mapped[Optional[str_list]] 
    required_soft_skills: Mapped[Optional[str_list]] 
    unacceptable_soft_skills: Mapped[Optional[str_list]] 

    # Competencies / Values
    job_competencies: Mapped[Optional[str_list]]
    corporate_competencies: Mapped[Optional[str_list]]
    critical_values: Mapped[Optional[str_list]]
    acceptable_behavior: Mapped[Optional[str_list]]
    unacceptable_behavior: Mapped[Optional[str_list]]
    fit_indicators: Mapped[Optional[str_list]]
    misfit_indicators: Mapped[Optional[str_list]]

    # Technical Requirements
    software: Mapped[Optional[str_list]]
    tools: Mapped[Optional[str_list]]
    languages: Mapped[Optional[str_list]]
    appearance: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Search Strategy
    keywords: Mapped[Optional[str_list]]
    similar_positions: Mapped[Optional[str_list]]
    stop_companies: Mapped[Optional[str_list]]
    donor_companies: Mapped[Optional[str_list]]
    referral_sources: Mapped[Optional[str_list]]

    # Work Conditions
    schedule: Mapped[str] = mapped_column(String, nullable=False)
    work_format: Mapped[str] = mapped_column(String, nullable=False)
    work_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    background_search: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    work_day_description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    business_trips_required: Mapped[Optional[bool]] = mapped_column(Boolean)
    business_trips_frequency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    business_trips_locations: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    salary_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gross: Mapped[Optional[bool]] = mapped_column(Boolean)
    bonus_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bonus_amount: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bonus_conditions: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    benefits: Mapped[Optional[str_list]]

    # Test Assignment
    test_required: Mapped[Optional[bool]] = mapped_column(Boolean)
    test_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_deadline: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    test_is_paid: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    #Status
    status: Mapped[HiringRequestStatus] = mapped_column(
        _pg_enum(HiringRequestStatus),
        nullable=False,
    )
    # TZ extras (additive; nullable for backward compatibility)
    planned_close_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_vacancy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    initiator_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    assigned_hr_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    assigned_hr_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    return_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    close_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class HiringRequestHistory(Base, TimestampMixin):
    """Append-only business history of request edits and workflow transitions."""

    __tablename__ = "hiring_request_history"

    id: Mapped[int_pk]
    hiring_request_id: Mapped[int] = mapped_column(
        ForeignKey("employee_requests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class HiringRequestInvite(Base, TimestampMixin):
    """One-time public invitation for a manager to create a hiring request."""

    __tablename__ = "hiring_request_invites"

    id: Mapped[int_pk]
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hiring_request_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employee_requests.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int_pk]
    type: Mapped[str] = mapped_column(String, nullable=False)
    employee_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    child_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    telegram_user: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    remind_before: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    # Optional clock time on the notify day (Europe/Samara). NULL = send as soon as day is due.
    remind_at_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Permanent events: every N day/week/month/year. Huey republishes when due.
    repeat_interval_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    repeat_interval_unit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    last_dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_dispatch_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class InterviewReminder(Base, TimestampMixin):
    """Scheduled HH.ru chat ping so the candidate does not miss the interview."""

    __tablename__ = "interview_reminders"
    __table_args__ = (
        Index("ix_interview_reminders_due", "is_send", "remind_at"),
    )

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    vacancy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vacancies.id"), nullable=True)
    interview_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    interview_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditLog(Base, TimestampMixin):
    """Immutable action trail for compliance / ops debugging."""

    __tablename__ = "audit_logs"

    id: Mapped[int_pk]
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CandidateStageHistory(Base, TimestampMixin):
    """Append-only candidate stage/status transitions."""

    __tablename__ = "candidate_stage_history"

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    from_stage: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    to_stage: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CandidateComment(Base, TimestampMixin):
    """Structured HR comments on a candidate (replaces JSON-in-hr_comment)."""

    __tablename__ = "candidate_comments"

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    author_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class PsychTestResult(Base, TimestampMixin):
    """
    Standalone psychological / work-behavior questionnaire result.
    Not linked to Candidate/Employee — free-form participant fields only.
    """

    __tablename__ = "psych_test_results"

    id: Mapped[int_pk]
    instrument_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    instrument_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[str] = mapped_column(String(200), nullable=False)
    taken_at: Mapped[date] = mapped_column(Date, nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    chs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    scores: Mapped[dict] = mapped_column(JSON, nullable=False)

    quality_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    leading_disc: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    leading_paei: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    leading_work10: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


class PublicTestResult(Base, TimestampMixin):
    """
    Standalone professional (Q&A) test result from a public take link.
    Not linked to Candidate — free-form participant fields only.
    """

    __tablename__ = "public_test_results"

    id: Mapped[int_pk]
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), nullable=False, index=True)
    test_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    position: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    taken_at: Mapped[date] = mapped_column(Date, nullable=False)

    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    integrity: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    test: Mapped["Test"] = relationship("Test")


class HhOAuthToken(Base, TimestampMixin):
    """Singleton row (id=1): durable HH.ru OAuth tokens (PG source of truth).

    Payload matches Redis ``hh_oauth_tokens``:
    ``{access_token, refresh_token, token_expires}``.

    ``version`` is the aggregate revision (not the OAuth token TTL and not the
    Redis JSON). It starts at 1 on insert and increments on every persist so
    callers can see which generation of the entity is stored. Token refresh
    uses last-write-wins; this is not an optimistic-lock that rejects writes.
    """

    __tablename__ = "hh_oauth_tokens"

    INITIAL_VERSION = 1

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False, default=1
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=INITIAL_VERSION, server_default="1"
    )

    def bump_version(self) -> int:
        self.version = int(self.version or 0) + 1
        return self.version


class CallConversation(Base, TimestampMixin):
    """Phone recording imported from T2 ATS, with STT transcript in ``payload``."""

    __tablename__ = "call_conversations"

    id: Mapped[int_pk]
    ats_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    call_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    call_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    caller_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    operator_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CallConversationStatus.pending.value,
        server_default=CallConversationStatus.pending.value,
        index=True,
    )
    ats_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    caller_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    operator_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class T2OAuthToken(Base, TimestampMixin):
    """Singleton row (id=1): durable T2 PBX OAuth tokens (PG source of truth).

    Same columns as ``hh_oauth_tokens``:
    ``id``, ``payload`` ``{access_token, refresh_token, token_expires}``,
    ``version``, plus ``created_at`` / ``updated_at`` from TimestampMixin.
    """

    __tablename__ = "t2_oauth_tokens"

    INITIAL_VERSION = 1

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False, default=1
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=INITIAL_VERSION, server_default="1"
    )

    def bump_version(self) -> int:
        self.version = int(self.version or 0) + 1
        return self.version


class TemporaryEmployee(Base, TimestampMixin):
    """Minimal employee record used before the authoritative ERP employee appears."""

    __tablename__ = "temporary_employees"

    id: Mapped[int_pk]
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    position: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    manager_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    manager_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unlinked", index=True)
    linked_employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    linked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class AdaptationEnrollment(Base, TimestampMixin):
    """One immutable adaptation history per hire or explicitly started transfer."""

    __tablename__ = "adaptation_enrollments"
    __table_args__ = (
        Index(
            "uq_adaptation_active_employee",
            "employee_id",
            unique=True,
            postgresql_where=text("employee_id IS NOT NULL AND closed = false AND archived = false"),
        ),
    )

    id: Mapped[int_pk]
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    temporary_employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("temporary_employees.id"), nullable=True, index=True
    )
    previous_enrollment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("adaptation_enrollments.id"), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    route: Mapped[str] = mapped_column(String(32), nullable=False, default="full", index=True)
    manager_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    manager_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    responsible_hr_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    responsible_hr_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    allow_personal_telegram_fallback: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    include_control_2m: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archive_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    risk: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    decision_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hiring_request_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employee_requests.id"), nullable=True, index=True
    )
    quota_credited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_credited_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee", back_populates="adaptation_enrollments"
    )
    temporary_employee: Mapped[Optional["TemporaryEmployee"]] = relationship()
    previous_enrollment: Mapped[Optional["AdaptationEnrollment"]] = relationship(
        remote_side="AdaptationEnrollment.id", uselist=False
    )
    checkpoints: Mapped[list["AdaptationCheckpoint"]] = relationship(
        "AdaptationCheckpoint",
        back_populates="enrollment",
        cascade="all, delete-orphan",
        order_by="AdaptationCheckpoint.plan_date",
    )


class AdaptationCheckpoint(Base, TimestampMixin):
    """A planned questionnaire slice (week 1, month 1/2, extra, control)."""

    __tablename__ = "adaptation_checkpoints"

    id: Mapped[int_pk]
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("adaptation_enrollments.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    series_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recurrence_rule: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fact_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    original_plan_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rescheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rescheduled_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reschedule_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    draft_ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    forced_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    forced_completed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    forced_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    risk_override: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    outcome_override: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    override_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    enrollment: Mapped["AdaptationEnrollment"] = relationship(
        "AdaptationEnrollment", back_populates="checkpoints"
    )
    answers: Mapped[list["AdaptationAnswer"]] = relationship(
        "AdaptationAnswer",
        back_populates="checkpoint",
        cascade="all, delete-orphan",
    )
    participant_forms: Mapped[list["AdaptationParticipantForm"]] = relationship(
        "AdaptationParticipantForm",
        back_populates="checkpoint",
        cascade="all, delete-orphan",
    )


class AdaptationAnswer(Base, TimestampMixin):
    """One submitted form per role on a checkpoint."""

    __tablename__ = "adaptation_answers"
    __table_args__ = (
        UniqueConstraint("checkpoint_id", "role", name="uq_adaptation_answer_role"),
    )

    id: Mapped[int_pk]
    checkpoint_id: Mapped[int] = mapped_column(
        ForeignKey("adaptation_checkpoints.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    checkpoint: Mapped["AdaptationCheckpoint"] = relationship(
        "AdaptationCheckpoint", back_populates="answers"
    )


class AdaptationAnswerVersion(Base, TimestampMixin):
    """Append-only snapshot; late answers and HR edits never erase history."""

    __tablename__ = "adaptation_answer_versions"
    __table_args__ = (UniqueConstraint("answer_id", "version", name="uq_adaptation_answer_version"),)

    id: Mapped[int_pk]
    answer_id: Mapped[int] = mapped_column(ForeignKey("adaptation_answers.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class AdaptationActionRecord(Base, TimestampMixin):
    __tablename__ = "adaptation_action_records"

    id: Mapped[int_pk]
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("adaptation_enrollments.id"), nullable=False, index=True)
    source_checkpoint_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("adaptation_checkpoints.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned", index=True)
    effect: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AdaptationParticipantForm(Base, TimestampMixin):
    __tablename__ = "adaptation_participant_forms"
    __table_args__ = (UniqueConstraint("checkpoint_id", "role", name="uq_adaptation_form_role"),)

    id: Mapped[int_pk]
    checkpoint_id: Mapped[int] = mapped_column(ForeignKey("adaptation_checkpoints.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    participant_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    token: Mapped[str] = mapped_column(String(96), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    checkpoint: Mapped["AdaptationCheckpoint"] = relationship(
        "AdaptationCheckpoint", back_populates="participant_forms"
    )


class AdaptationNotificationTemplate(Base, TimestampMixin):
    __tablename__ = "adaptation_notification_templates"
    __table_args__ = (UniqueConstraint("audience", "event", name="uq_adaptation_template_audience_event"),)

    id: Mapped[int_pk]
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    event: Mapped[str] = mapped_column(String(48), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AdaptationNotificationDelivery(Base, TimestampMixin):
    __tablename__ = "adaptation_notification_deliveries"
    __table_args__ = (
        UniqueConstraint("checkpoint_id", "role", "event", name="uq_adaptation_delivery_event"),
    )

    id: Mapped[int_pk]
    checkpoint_id: Mapped[int] = mapped_column(ForeignKey("adaptation_checkpoints.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    event: Mapped[str] = mapped_column(String(48), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AdaptationRoutingDecision(Base, TimestampMixin):
    """Auditable dry-run recipient resolution; it never sends a notification."""

    __tablename__ = "adaptation_routing_decisions"

    id: Mapped[int_pk]
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("adaptation_enrollments.id"), nullable=False, index=True)
    checkpoint_id: Mapped[Optional[int]] = mapped_column(ForeignKey("adaptation_checkpoints.id"), nullable=True, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    selected_contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contact_points.id"), nullable=True)
    resolved_recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_recipient_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="resolved")
    decided_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class AdaptationReportDocument(Base, TimestampMixin):
    __tablename__ = "adaptation_report_documents"
    __table_args__ = (
        UniqueConstraint("checkpoint_id", "document_type", "format", "version", name="uq_adaptation_document_version"),
    )

    id: Mapped[int_pk]
    checkpoint_id: Mapped[Optional[int]] = mapped_column(ForeignKey("adaptation_checkpoints.id"), nullable=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("adaptation_enrollments.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(48), nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, unique=True)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class AdaptationModuleSettings(Base, TimestampMixin):
    __tablename__ = "adaptation_module_settings"

    id: Mapped[int_pk]
    overdue_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    overdue_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(9, 0))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Samara")
    visible_columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    show_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    file_name_templates: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    signature_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: ["HR", "Руководитель", "Директор"])
    risk_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    allow_personal_telegram_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_role: Mapped[str] = mapped_column(String(32), nullable=False, default="hr")
    manual_share_confirmation_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)


class CandidateAiEvaluation(Base, TimestampMixin):
    """Persisted AI score/comment for a candidate on a vacancy."""

    __tablename__ = "candidate_ai_evaluations"
    __table_args__ = (
        UniqueConstraint("correlation_id", name="uq_candidate_ai_evaluations_correlation"),
    )

    id: Mapped[int_pk]
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    vacancy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vacancies.id"), nullable=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="candidate.assigned")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    candidate: Mapped["Candidate"] = relationship(back_populates="ai_evaluations")
    vacancy: Mapped[Optional["Vacancy"]] = relationship()


class OutboxMessage(Base, TimestampMixin):
    """Transactional outbox for reliable RabbitMQ publishing."""

    __tablename__ = "outbox_messages"
    __table_args__ = (
        UniqueConstraint("correlation_id", "event_type", name="uq_outbox_correlation_event"),
    )

    id: Mapped[int_pk]
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False, default="candidate_evaluation")
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
