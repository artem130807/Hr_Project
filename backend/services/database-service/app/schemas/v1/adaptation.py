from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AdaptationEnrollIn(BaseModel):
    employee_id: Optional[int] = None
    erp_user_id: Optional[str] = Field(default=None, max_length=36)
    include_control_2m: bool = False
    route: str = "full"
    extra_on: Optional[date] = None
    start_date: Optional[date] = None
    manager_user_id: Optional[str] = Field(default=None, max_length=36)
    manager_name: Optional[str] = Field(default=None, max_length=200)
    hiring_request_id: Optional[int] = None

    @model_validator(mode="after")
    def require_staff_ref(self):
        if self.employee_id is None and not (self.erp_user_id or "").strip():
            raise ValueError("Укажите employee_id или erp_user_id")
        return self


class AdaptationExtraIn(BaseModel):
    enrollment_id: int
    plan_date: date
    kind: str = "extra"
    frequency: str = "once"
    repeat_count: int = Field(default=1, ge=1, le=52)
    interval_days: Optional[int] = Field(default=None, ge=1, le=365)
    series_key: Optional[str] = Field(default=None, min_length=8, max_length=64)
    include_hr: bool = False


class AdaptationAnswerIn(BaseModel):
    role: str
    payload: dict = Field(default_factory=dict)


class AdaptationRescheduleIn(BaseModel):
    plan_date: date
    reason: str = Field(min_length=3, max_length=2000)


class AdaptationForceCompleteIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class AdaptationFinalizeIn(BaseModel):
    outcome: str
    risk: str
    comment: Optional[str] = Field(default=None, max_length=4000)
    credit_hiring_request: bool = False


class AdaptationManagerChangeIn(BaseModel):
    manager_user_id: str = Field(min_length=1, max_length=36)
    manager_name: Optional[str] = Field(default=None, max_length=200)


class AdaptationActionIn(BaseModel):
    action: str = Field(min_length=2, max_length=4000)
    owner_user_id: Optional[str] = Field(default=None, max_length=36)
    owner_name: Optional[str] = Field(default=None, max_length=200)
    due_date: Optional[date] = None


class AdaptationActionUpdate(BaseModel):
    status: str
    effect: Optional[str] = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_status(self):
        if self.status not in {"planned", "in_progress", "done", "cancelled"}:
            raise ValueError("Некорректный статус действия")
        return self


class AdaptationArchiveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class AdaptationRestartIn(BaseModel):
    start_date: date
    reason: str = Field(min_length=3, max_length=2000)
    route: str = "full"


class TemporaryEmployeeIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    position: str = Field(min_length=1, max_length=200)
    department: str = Field(min_length=1, max_length=200)
    start_date: date
    manager_user_id: Optional[str] = Field(default=None, max_length=36)
    manager_name: Optional[str] = Field(default=None, max_length=200)
    photo_url: Optional[str] = None
    route: str = "full"


class TemporaryEmployeeLinkIn(BaseModel):
    employee_id: int


class AdaptationSettingsUpdate(BaseModel):
    overdue_enabled: Optional[bool] = None
    overdue_time: Optional[str] = None
    timezone: Optional[str] = None
    visible_columns: Optional[list[str]] = None
    show_photo: Optional[bool] = None
    file_name_templates: Optional[dict] = None
    signature_roles: Optional[list[str]] = None
    risk_rules: Optional[dict] = None
    allow_personal_telegram_fallback: Optional[bool] = None
    fallback_role: Optional[str] = Field(default=None, pattern="^hr$")
    manual_share_confirmation_hours: Optional[int] = Field(default=None, ge=1, le=720)


class AdaptationRotateTokenIn(BaseModel):
    confirmed: bool
    reason: str = Field(min_length=3, max_length=500)


class AdaptationTemplateUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    enabled: bool = True


class AdaptationDocumentGenerateIn(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["docx", "pdf"])
    document_types: Optional[list[str]] = None
    final: bool = False
    idempotency_key: Optional[str] = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_formats(self):
        normalized = list(dict.fromkeys(str(item).lower() for item in self.formats))
        if not normalized or any(item not in {"docx", "pdf"} for item in normalized):
            raise ValueError("Поддерживаются форматы docx и pdf")
        self.formats = normalized
        if self.document_types is not None:
            self.document_types = list(dict.fromkeys(str(item).lower() for item in self.document_types))
        return self


class AdaptationAnswerRead(BaseModel):
    id: int
    role: str
    payload: dict
    submitted_at: datetime

    class Config:
        from_attributes = True


class AdaptationProgressDot(BaseModel):
    role: str
    state: str  # waiting | done | muted
    label: str


class AdaptationCheckpointRead(BaseModel):
    id: int
    enrollment_id: int
    employee_id: Optional[int]
    temporary_employee_id: Optional[int] = None
    full_name: str = ""
    department: str = ""
    position: str = ""
    date_hired: Optional[date] = None
    date_fired: Optional[date] = None
    photo_url: Optional[str] = None
    kind: str
    kind_label: str
    plan_date: date
    fact_date: Optional[date] = None
    status: str
    status_label: str
    risk: str
    risk_label: str
    risk_signals: dict = Field(default_factory=dict)
    outcome: str
    progress: list[AdaptationProgressDot]
    answers: list[AdaptationAnswerRead] = Field(default_factory=list)
    form: Optional[dict] = None
    form_title: Optional[dict] = None
    form_links: list[dict] = Field(default_factory=list)
    talk_hr: bool = False
    route: str = "full"
    core_history: Optional[dict] = None
    original_plan_date: Optional[date] = None
    reschedule_reason: Optional[str] = None
    forced_reason: Optional[str] = None
    manager_user_id: Optional[str] = None
    manager_name: Optional[str] = None
    available_actions: list[str] = Field(default_factory=list)
    archived: bool = False


class AdaptationAttention(BaseModel):
    overdue: int
    this_week: int
    ready_hr: int


class AdaptationListResponse(BaseModel):
    period_label: str
    year: int
    month: int
    attention: AdaptationAttention
    items: list[AdaptationCheckpointRead]
    total: int = 0
    page: int = 1
    page_size: int = 100
