"""Periodic cleanup for unsubmitted private document drafts."""
from app.worker.huey import huey
from app.worker.jobs import run_candidate_document_drafts_purge
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(interval_crontab(60), name="hr.candidate_documents.purge_drafts")
def tick_candidate_document_drafts_purge() -> int:
    return run_async(run_candidate_document_drafts_purge())
