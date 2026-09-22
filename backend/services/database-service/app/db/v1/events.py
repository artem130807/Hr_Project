from sqlalchemy import event
from datetime import datetime, timezone
from sqlalchemy.orm.attributes import NEVER_SET
from app.db.v1.models import CandidateVacancyRelation


@event.listens_for(CandidateVacancyRelation.status, "set", propagate=True)
def update_status_ts(target, value, oldvalue, initiator):
    if oldvalue is NEVER_SET:
        return value

    if value != oldvalue:
        target.status_updated_at = datetime.now(timezone.utc)

    return value