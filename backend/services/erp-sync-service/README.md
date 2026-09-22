# Moved

ERP user sync is no longer a separate microservice.

Periodic sync runs in the **Huey worker** (`hr-worker` / `huey_consumer app.worker.app.huey`):

- `app/erp/` — ERP client, mapper, create-only sync
- `app/worker/jobs.py` — `run_erp_user_sync`
- `app/worker/tasks/erp_sync.py` — Huey schedule
- Manual trigger: `POST /v1/admin/users/erp-sync/run`

Configure `ERP_BASE`, `ERP_BEARER_TOKEN` (or API key) on **database-service** (same env as the worker).
