from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger
from app.db.middleware import get_db
from app.db.v1.enums import CandidateStage, CandidateStatus, HiringRequestStatus
from app.db.v1.models import Candidate, CandidateVacancyRelation, EmployeeRequest, Event, Vacancy
from app.schemas.v1.stats import CandidateStatsResponse
from app.utils.stats import build_funnel_xlsx, get_candidate_status_summary, get_funnel_data

router = APIRouter()

EVENT_TYPE_LABELS = {
    "birthday": "День рождения",
    "child_birthday": "День рождения ребенка",
    "work_anniversary": "Годовщина работы",
    "interview": "Собеседование",
    "permanent": "Постоянное событие",
    "other": "Другое событие",
}


def _event_type_label(raw_type: str | None) -> str:
    key = str(raw_type or "").strip().lower()
    if key in EVENT_TYPE_LABELS:
        return EVENT_TYPE_LABELS[key]
    if not key:
        return "Событие"
    return key.replace("_", " ").capitalize()


def _format_event_date_ru(value: date | None) -> str:
    if not value:
        return "—"
    return value.strftime("%d.%m.%Y")


class DashboardTask(BaseModel):
    id: str
    group: str
    title: str
    description: str
    priority: str
    href: str
    meta: str | None = None


class DashboardSummary(BaseModel):
    active_vacancies: int = 0
    candidates_in_work: int = 0
    pending_offers: int = 0
    overdue_tasks: int = 0


class DashboardResponse(BaseModel):
    summary: DashboardSummary
    tasks: list[DashboardTask] = Field(default_factory=list)


@router.get("/analytics/active-candidates", response_model=CandidateStatsResponse)
async def get_active_candidates_stats(
    vacancy_id: int | None = Query(None, gt=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        stats = await get_candidate_status_summary(db, vacancy_id=vacancy_id)
        return {"stats": stats}
    except HTTPException as e:
        logger.error(f"Error {e.status_code} analyzing: {str(e)}")
        raise
    except Exception as e:
        raise HTTPException(500, f"Error analyzing: {str(e)}")


@router.get("/analytics/dashboard", response_model=DashboardResponse)
async def get_dashboard_tasks(db: AsyncSession = Depends(get_db)):
    """Live home tasks for TZ dashboard (aggregates existing entities)."""
    try:
        return await _build_dashboard(db)
    except Exception as e:
        logger.exception("Dashboard aggregate failed: %s", e)
        # Never break the home page with opaque Failed to fetch / 502
        return DashboardResponse(
            summary=DashboardSummary(),
            tasks=[
                DashboardTask(
                    id="dashboard-error",
                    group="vacancies",
                    title="Не удалось собрать задачи",
                    description=str(e)[:300],
                    priority="low",
                    href="/dashboard",
                    meta="ошибка",
                )
            ],
        )


async def _build_dashboard(db: AsyncSession) -> DashboardResponse:
    today = date.today()
    tasks: list[DashboardTask] = []

    try:
        req_rows = (
            await db.execute(
                select(EmployeeRequest).where(
                    EmployeeRequest.status.notin_(
                        [
                            HiringRequestStatus.closed.value,
                            HiringRequestStatus.completed.value,
                        ]
                    )
                )
            )
        ).scalars().all()
    except Exception as e:
        logger.warning("Dashboard: hiring requests query failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        req_rows = []

    for req in req_rows:
        status_val = req.status.value if hasattr(req.status, "value") else str(req.status)
        if req.status in (HiringRequestStatus.created, HiringRequestStatus.on_analysis) or status_val in (
            HiringRequestStatus.created.value,
            HiringRequestStatus.on_analysis.value,
        ):
            tasks.append(
                DashboardTask(
                    id=f"req-approve-{req.id}",
                    group="vacancies",
                    title=f"Согласование заявки З-{req.id}",
                    description=f"{req.position} · {req.department}",
                    priority="medium",
                    href="/requests",
                    meta=status_val,
                )
            )
        close = getattr(req, "planned_close_date", None)
        if close and close < today:
            tasks.append(
                DashboardTask(
                    id=f"req-overdue-{req.id}",
                    group="vacancies",
                    title=f"Просрочен дедлайн заявки З-{req.id}",
                    description=f"{req.position}: плановое закрытие {close.isoformat()}",
                    priority="high",
                    href="/requests",
                    meta="просрочено",
                )
            )

    try:
        vac_q = select(Vacancy).where(Vacancy.hh_vacancy_id.is_(None))
        # is_template may be missing on old DBs before startup ALTER
        if hasattr(Vacancy, "is_template"):
            vac_q = vac_q.where(
                or_(Vacancy.is_template.is_(False), Vacancy.is_template.is_(None))
            )
        vac_rows = (await db.execute(vac_q)).scalars().all()
    except Exception as e:
        logger.warning("Dashboard: vacancies query failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        vac_rows = []

    for vac in vac_rows[:20]:
        close = getattr(vac, "planned_close_date", None)
        if close and close <= today:
            tasks.append(
                DashboardTask(
                    id=f"vac-publish-{vac.id}",
                    group="vacancies",
                    title=f"Просрочена публикация В-{vac.id}",
                    description=vac.name,
                    priority="high",
                    href="/vacancies",
                    meta="не на HH.ru",
                )
            )

    try:
        offer_waiting = (
            await db.execute(
                select(func.count())
                .select_from(CandidateVacancyRelation)
                .where(
                    CandidateVacancyRelation.status.in_(
                        [
                            CandidateStatus.interview.value,
                            CandidateStatus.test_passed.value,
                            CandidateStatus.applied.value,
                        ]
                    ),
                    CandidateVacancyRelation.is_active.is_(True),
                )
            )
        ).scalar() or 0
    except Exception as e:
        logger.warning("Dashboard: offers count failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        offer_waiting = 0

    try:
        in_work = (
            await db.execute(
                select(func.count())
                .select_from(Candidate)
                .where(Candidate.stage == CandidateStage.employment)
            )
        ).scalar() or 0
    except Exception as e:
        logger.warning("Dashboard: in_work count failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        in_work = 0

    try:
        active_vac = (
            await db.execute(
                select(func.count()).select_from(Vacancy).where(Vacancy.hh_vacancy_id.is_not(None))
            )
        ).scalar() or 0
    except Exception as e:
        logger.warning("Dashboard: active vacancies count failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        active_vac = 0

    if offer_waiting:
        tasks.append(
            DashboardTask(
                id="cand-offers",
                group="candidates",
                title="Офферы / решения ожидают ответа",
                description=f"{offer_waiting} кандидат(ов) на этапе решения",
                priority="medium",
                href="/candidates",
                meta=str(offer_waiting),
            )
        )

    try:
        soon = today + timedelta(days=7)
        events = (
            await db.execute(
                select(Event).where(
                    Event.event_date >= today,
                    Event.event_date <= soon,
                    Event.is_done.is_(False),
                )
            )
        ).scalars().all()
    except Exception as e:
        logger.warning("Dashboard: events query failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        events = []

    for ev in events[:10]:
        event_label = _event_type_label(getattr(ev, "type", None))
        date_ru = _format_event_date_ru(getattr(ev, "event_date", None))
        tasks.append(
            DashboardTask(
                id=f"event-{ev.id}",
                group="calendar",
                title=f"{event_label}: {ev.employee_name or 'событие'}",
                description=f"Дата {date_ru}",
                priority="low",
                href="/events",
                meta=date_ru,
            )
        )

    overdue = sum(1 for t in tasks if t.priority == "high")
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda t: (priority_rank.get(t.priority, 9), t.title))

    return DashboardResponse(
        summary=DashboardSummary(
            active_vacancies=int(active_vac),
            candidates_in_work=int(in_work),
            pending_offers=int(offer_waiting),
            overdue_tasks=overdue,
        ),
        tasks=tasks[:40],
    )


@router.get("/analytics/funnel/export")
async def export_candidate_funnel(
    db: AsyncSession = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    vacancy_id: int | None = Query(None, gt=0),
):
    try:
        dt_from = datetime.combine(date_from, time.min) if date_from else None
        dt_to = datetime.combine(date_to, time(23, 59, 59)) if date_to else None

        funnel_data, detail_data = await get_funnel_data(
            db,
            dt_from,
            dt_to,
            vacancy_id=vacancy_id,
        )
        temp_path = build_funnel_xlsx(funnel_data, detail_data, dt_from, dt_to)

        filename = "candidate_funnel.xlsx"
        if date_from and date_to:
            filename = f"candidate_funnel_{date_from}_{date_to}.xlsx"

        return FileResponse(
            temp_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )

    except HTTPException as e:
        logger.error(f"Error {e.status_code} generating funel: {str(e)}")
        raise
    except Exception as e:
        raise HTTPException(500, f"Error generating funnel: {str(e)}")
