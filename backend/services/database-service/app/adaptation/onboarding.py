"""Build the initial adaptation graph inside the employee creation transaction.

Only call for newly created employees: existing staff imports must not trigger
retroactive questionnaires. No commit or external delivery happens here.
"""
import re

from app.adaptation.rules import plan_date_for, roles_for_kind
from app.db.v1.models import AdaptationEnrollment, AdaptationCheckpoint, AdaptationParticipantForm


def initial_route(position: str | None) -> str:
    words = set(re.findall(r"[а-яё]+", (position or "").lower()))
    control_stems = ("водител", "строител", "электр", "слесар", "механик")
    return "control" if any(word.startswith(control_stems) for word in words) else "full"


def enroll_new_employee(db, employee, *, route: str | None = None):
    if employee.date_fired or not employee.date_hired:
        return None
    route = route or initial_route(employee.position)
    enrollment = AdaptationEnrollment(
        employee_id=employee.id, start_date=employee.date_hired, route=route,
        include_control_2m=route == "control",
    )
    for kind in (["control_2m"] if route == "control" else ["week_1", "month_1", "month_2"]):
        planned = plan_date_for(kind, employee.date_hired)
        checkpoint = AdaptationCheckpoint(kind=kind, plan_date=planned, original_plan_date=planned)
        checkpoint.participant_forms = [
            AdaptationParticipantForm(role=role, participant_user_id=(employee.erp_user_id if role == "employee" else None))
            for role in roles_for_kind(kind)
        ]
        enrollment.checkpoints.append(checkpoint)
    db.add(enrollment)
    return enrollment
