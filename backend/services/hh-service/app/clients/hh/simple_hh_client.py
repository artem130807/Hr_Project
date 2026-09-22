import httpx
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Sequence, Union

from fastapi import HTTPException

from app import config
from app import mock
from app.app_logging import logger

OFFER_LETTER_HEADING = "Приглашаем вас на работу"
_INTERVIEW_HEADING_ALIASES = frozenset(
    {
        "собеседование",
        "приглашение на собеседование",
    }
)


def apply_offer_letter_heading(message: Optional[str]) -> str:
    """Guarantee hh.ru letter body starts with the job-offer heading, not interview."""
    text = str(message or "").strip()
    if not text:
        return OFFER_LETTER_HEADING
    lines = text.splitlines()
    first = lines[0].strip().rstrip(":").strip()
    if first.casefold() == OFFER_LETTER_HEADING.casefold():
        return text
    if first.casefold() in _INTERVIEW_HEADING_ALIASES:
        rest = "\n".join(lines[1:]).strip()
        return f"{OFFER_LETTER_HEADING}\n\n{rest}" if rest else OFFER_LETTER_HEADING
    return f"{OFFER_LETTER_HEADING}\n\n{text}"

class HHTokenManager:
    REDIS_KEY = "hh_oauth_tokens"
    DB_TOKENS_PATH = "/hh-oauth/tokens"
    DEFINITIVE_OAUTH_ERRORS = frozenset({"invalid_grant", "invalid_request", "invalid_client"})
    PLACEHOLDER_TOKEN_PREFIX = "fake-hh-"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        redis_client=None,
        db_client=None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._redis = redis_client
        self._db = db_client

        now = datetime.now(timezone.utc)
        self.token_expires = (
            now + timedelta(seconds=expires_in) if expires_in else now
        )

        self.token_url = "https://api.hh.ru/token"

    def _payload(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires": self.token_expires.isoformat() if self.token_expires else None,
        }

    @classmethod
    def is_definitive_oauth_failure(
        cls, status_code: int, body_text: str, error: Optional[str] = None
    ) -> bool:
        """True only when HH revoked the grant — safe to wipe stored tokens."""
        if status_code not in (400, 401):
            return False
        err = (error or "").strip().lower()
        text = (body_text or "").lower()
        return err in cls.DEFINITIVE_OAUTH_ERRORS or "token not found" in text

    @classmethod
    def is_placeholder_token(cls, value: Optional[str]) -> bool:
        """Cluster secret stubs like ``fake-hh-access-token`` must never be persisted."""
        raw = (value or "").strip().lower()
        return bool(raw) and raw.startswith(cls.PLACEHOLDER_TOKEN_PREFIX)

    async def _save_tokens(self):
        """Dual-write: Redis cache + PostgreSQL (source of truth, best-effort)."""
        if self.is_placeholder_token(self.access_token) or self.is_placeholder_token(self.refresh_token):
            logger.warning("HH tokens not saved: placeholder/fake values from env")
            return
        payload = self._payload()
        if self._redis:
            try:
                await self._redis.set(self.REDIS_KEY, json.dumps(payload))
                logger.info("HH tokens saved to Redis")
            except Exception as e:
                logger.warning("Failed to save HH tokens to Redis: %s", e)
        if self._db:
            try:
                saved = await self._db.put(self.DB_TOKENS_PATH, json=payload)
                if saved is None:
                    logger.warning(
                        "HH tokens PostgreSQL PUT returned empty (HTTP error); Redis cache may be the only copy"
                    )
                else:
                    logger.info("HH tokens saved to PostgreSQL (source of truth)")
            except Exception as e:
                logger.warning("Failed to save HH tokens to PostgreSQL: %s", e)

    async def _clear_tokens(self):
        """Wipe in-memory + Redis + PG after a definitive OAuth failure."""
        logger.warning("HH tokens cleared")
        self.access_token = None
        self.refresh_token = None
        self.token_expires = datetime.now(timezone.utc)
        if self._redis:
            try:
                await self._redis.delete(self.REDIS_KEY)
            except Exception as e:
                logger.warning("Failed to delete HH tokens from Redis: %s", e)
        if self._db:
            try:
                await self._db.delete(self.DB_TOKENS_PATH)
            except Exception as e:
                logger.warning("Failed to delete HH tokens from PostgreSQL: %s", e)

    @classmethod
    async def load_from_redis(cls, redis_client) -> dict:
        """Загружает сохранённые токены из Redis. Возвращает dict или {}."""
        try:
            raw = await redis_client.get(cls.REDIS_KEY)
            if not raw:
                return {}
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Failed to load HH tokens from Redis: {e}")
            return {}

    @classmethod
    async def load_from_db(cls, db_client) -> dict:
        """Load tokens from database-service. Returns payload dict or {}."""
        if db_client is None:
            return {}
        try:
            data = await db_client.get(cls.DB_TOKENS_PATH)
        except Exception as e:
            logger.warning("Failed to load HH tokens from PostgreSQL: %s", e)
            return {}
        if not isinstance(data, dict):
            return {}
        payload = data.get("payload")
        if not isinstance(payload, dict) or not payload.get("access_token"):
            return {}
        return payload

    async def get_token(self) -> str:
        """Return a live access token, refreshing when expired."""
        now = datetime.now(timezone.utc)
        expires = self.token_expires
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
            self.token_expires = expires
        if self.access_token and expires is not None and now < expires:
            return self.access_token
        if not self.refresh_token:
            raise HTTPException(
                status_code=502,
                detail=(
                    "HH.ru не подключён. Нажмите «Войти в HH» в меню "
                    "и авторизуйте приложение работодателя."
                ),
            )
        try:
            return await self._refresh_tokens()
        except HTTPException:
            raise
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

    async def _refresh_tokens(self) -> str:
        if not self.refresh_token:
            raise RuntimeError("Нет refresh_token — токены отсутствуют.")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.RequestError as e:
            logger.error("HH token refresh network error (tokens kept): %s", e)
            raise RuntimeError(f"Не удалось обновить токен HH (сеть): {e}") from e

        if resp.status_code != 200:
            error = None
            try:
                body = resp.json()
                if isinstance(body, dict):
                    error = body.get("error")
            except Exception:
                pass
            logger.error("HH token refresh error: %s %s", resp.status_code, resp.text)
            if self.is_definitive_oauth_failure(resp.status_code, resp.text, error):
                await self._clear_tokens()
                raise RuntimeError(
                    f"Не удалось обновить токен HH: {resp.status_code} {resp.text}"
                )
            logger.warning("HH token refresh transient — tokens kept")
            raise RuntimeError(
                f"Не удалось обновить токен HH (transient): {resp.status_code} {resp.text}"
            )

        data = resp.json()
        logger.info("HH token refreshed successfully")

        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        self.token_expires = datetime.now(timezone.utc) + timedelta(
            seconds=data["expires_in"]
        )

        await self._save_tokens()
        return self.access_token

class SimpleHHClient:
    BASE_URL = "https://api.hh.ru"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        employer_id: Optional[int] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        redis_client=None,
        db_client=None,
    ):
        self.employer_id = employer_id
        self.token_manager = HHTokenManager(
            client_id, client_secret, access_token, refresh_token, expires_in,
            redis_client=redis_client,
            db_client=db_client,
        )
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=15.0)

    async def _auth_headers(self) -> dict[str, str]:
        token = await self.token_manager.get_token()
        app = config.HH_APP_NAME or "HR-Bot"
        ver = config.HH_APP_VERSION or "1.0"
        email = config.HH_EMAIL or "hr@localhost"
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": f"{app}/{ver} ({email})",
            "HH-User-Agent": f"{app}/{ver} ({email})",
        }

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        headers = await self._auth_headers()
        kwargs["headers"] = {**headers, **kwargs.get("headers", {})}

        resp = await self.client.request(method, path, **kwargs)

        # ========== HANDLING 401 ==========
        if resp.status_code == 401:
            try:
                await self.token_manager.get_token()  # попытка refresh
            except Exception:
                # refresh провалился, токен очищен — not a platform user session error
                raise HTTPException(502, "HH token invalid or revoked — авторизуйте приложение HH.ru заново")

            # retry с новым токеном
            kwargs["headers"]["Authorization"] = (
                f"Bearer {self.token_manager.access_token}"
            )
            resp = await self.client.request(method, path, **kwargs)
            if resp.status_code == 401:
                raise HTTPException(502, "HH token invalid or revoked — авторизуйте приложение HH.ru заново")

        # ========== HANDLING OTHER ERRORS ==========
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, f"HH API Error {resp.text}")

        if resp.status_code == 204:
            return None
        if resp.status_code in (200, 201) and not resp.content:
            return {"status": "ok", "http_status": resp.status_code}

        try:
            return resp.json()
        except Exception:
            return {"status": "ok", "http_status": resp.status_code}

    # === CRUD по вакансиям ===
    async def post_vacancy_draft(self, vacancy_data: dict) -> dict:
        return await self._request("POST", "/vacancies/drafts", json=vacancy_data)
    
    async def post_vacancy(self, vacancy_data: dict) -> dict:
        if config.MOCK_HH:
            logger.info(f"Return mock POST /vacancies response (MOCK_HH=true)")
            return mock.post_vacancy_response
        logger.info(f"Posting vacancy to HH API (ENV={config.ENV})")
        return await self._request("POST", "/vacancies", json=vacancy_data)

    async def get_vacancy(self, vacancy_id: str) -> dict:
        if config.MOCK_HH:
            logger.info(f"Return mock GET /vacancies response (MOCK_HH=true)")
            return mock.hh_vacancy_get_response
        return await self._request("GET", f"/vacancies/{vacancy_id}")

    async def update_vacancy(self, vacancy_id: str, update_data: dict) -> dict:
        if config.MOCK_HH:
            logger.info(f"Return mock PUT /vacancies/{vacancy_id} (MOCK_HH=true)")
            return {"id": str(vacancy_id), **(update_data or {})}
        return await self._request("PUT", f"/vacancies/{vacancy_id}", json=update_data)

    async def archive_vacancy(self, vacancy_id: str) -> dict | None:
        """Archive vacancy on HH (remove from active publications)."""
        if config.MOCK_HH:
            logger.info(f"Return mock archive vacancy {vacancy_id} (MOCK_HH=true)")
            return {"status": "archived", "id": str(vacancy_id)}
        return await self._request("PUT", f"/vacancies/archived/{vacancy_id}")

    async def hide_vacancy(self, vacancy_id: str) -> dict | None:
        """Hide (delete) vacancy on HH."""
        if config.MOCK_HH:
            logger.info(f"Return mock hide vacancy {vacancy_id} (MOCK_HH=true)")
            return {"status": "hidden", "id": str(vacancy_id)}
        return await self._request("PUT", f"/vacancies/hidden/{vacancy_id}")

    async def delete_vacancy(self, vacancy_id: str) -> dict | None:
        """Remove vacancy from HH: archive, then hide. Tolerates already-removed state."""
        archived = None
        hidden = None
        try:
            archived = await self.archive_vacancy(vacancy_id)
        except HTTPException as e:
            if e.status_code not in (404, 400, 403):
                raise
            logger.warning(f"Archive vacancy {vacancy_id} skipped: {e.detail}")
        try:
            hidden = await self.hide_vacancy(vacancy_id)
        except HTTPException as e:
            if e.status_code not in (404, 400, 403):
                raise
            logger.warning(f"Hide vacancy {vacancy_id} skipped: {e.detail}")
        return {"archived": archived, "hidden": hidden}

    async def resolve_employer_id(self) -> str:
        """Employer id from config, else from HH /me (authoritative for current token)."""
        configured = str(self.employer_id).strip() if self.employer_id not in (None, "") else ""
        if configured:
            return configured
        me = await self.get_me()
        if not isinstance(me, dict):
            raise HTTPException(502, "HH /me returned empty body")
        employer = me.get("employer") if isinstance(me.get("employer"), dict) else {}
        eid = employer.get("id")
        if not eid:
            raise HTTPException(
                400,
                "Не удалось определить employer_id: задайте EMPLOYER_ID или авторизуйтесь токеном работодателя",
            )
        self.employer_id = str(eid)
        return str(eid)

    async def list_employer_vacancies(
        self,
        *,
        archived: bool = False,
        page: int = 0,
        per_page: int = 50,
        employer_id: Optional[str | int] = None,
        all_accessible: bool = True,
        manager_id: Optional[str] = None,
        manager_ids: Optional[str] = None,
        text: Optional[str] = None,
    ) -> dict:
        """Список активных/архивных вакансий работодателя на HH.ru.

        HH API default (without all_accessible / manager_ids) returns only the
        **current manager's** vacancies. For the HR panel we want company-wide
        access: pass all_accessible=true on the active list.
        """
        if config.MOCK_HH:
            return {
                "items": [],
                "found": 0,
                "pages": 0,
                "page": page,
                "per_page": per_page,
            }

        # Prefer explicit arg → cached/config → /me
        if employer_id not in (None, ""):
            eid = str(employer_id)
        else:
            eid = await self.resolve_employer_id()
            # If config was wrong/stale, also try /me when primary call 404s
            me_employer_id = None
            try:
                me = await self.get_me()
                if isinstance(me, dict) and isinstance(me.get("employer"), dict):
                    me_employer_id = me["employer"].get("id")
                    if me_employer_id:
                        me_employer_id = str(me_employer_id)
                        # Prefer /me when it disagrees with env (common misconfig)
                        if me_employer_id != eid:
                            logger.warning(
                                "EMPLOYER_ID=%s differs from /me employer.id=%s — using /me",
                                eid,
                                me_employer_id,
                            )
                            eid = me_employer_id
                            self.employer_id = eid
            except Exception as e:
                logger.warning("Could not cross-check employer via /me: %s", e)

        kind = "archived" if archived else "active"
        # Active list max per_page is 50 per HH OpenAPI; archived allows more.
        capped = min(int(per_page or 50), 50 if not archived else 1000)
        params: dict[str, Any] = {"page": page, "per_page": capped}
        if text:
            params["text"] = text
        # manager filters and all_accessible are mutually exclusive on HH side
        if manager_ids:
            params["manager_ids"] = str(manager_ids)
        elif manager_id:
            params["manager_id"] = str(manager_id)
        elif not archived and all_accessible:
            # Include vacancies of managers the token can access (not only /me).
            params["all_accessible"] = "true"

        path = f"/employers/{eid}/vacancies/{kind}"

        async def _call(call_params: dict) -> dict:
            return await self._request("GET", path, params=call_params)

        try:
            return await _call(params)
        except HTTPException as e:
            # Rights for all_accessible may be missing — fall back to current manager.
            if (
                not archived
                and params.get("all_accessible")
                and e.status_code in (400, 403)
            ):
                logger.warning(
                    "HH all_accessible rejected (%s) — retrying current-manager list",
                    e.status_code,
                )
                fallback = {k: v for k, v in params.items() if k != "all_accessible"}
                try:
                    data = await _call(fallback)
                    if isinstance(data, dict):
                        data = {**data, "_all_accessible_fallback": True}
                    return data
                except HTTPException:
                    pass
            # Fallback: some accounts only expose ?archived= on /vacancies
            if e.status_code == 404 and not archived:
                try:
                    return await self._request(
                        "GET",
                        f"/employers/{eid}/vacancies",
                        params={**params, "archived": "false"},
                    )
                except HTTPException:
                    pass
            detail = e.detail
            raise HTTPException(
                e.status_code,
                (
                    f"HH employer vacancies failed for employer_id={eid}: {detail}. "
                    "Проверьте EMPLOYER_ID и что токен — работодателя (не соискателя)."
                ),
            ) from e

    async def list_vacancies(self, params: dict | None = None) -> dict:
        """Alias: active employer vacancies (GET, not POST /vacancies)."""
        params = params or {}
        return await self.list_employer_vacancies(
            archived=bool(params.get("archived")),
            page=int(params.get("page") or 0),
            per_page=int(params.get("per_page") or 50),
        )

    async def get_negotiations_meta(self, vacancy_id: str) -> dict:
        """Метаданные коллекций откликов по вакансии HH."""
        return await self._request("GET", "/negotiations", params={"vacancy_id": str(vacancy_id)})

    async def list_negotiations_collection(
        self,
        collection_path: str,
        *,
        page: int = 0,
        per_page: int = 50,
    ) -> dict:
        """Страница коллекции переговоров (path относительно api.hh.ru)."""
        path = collection_path.strip()
        for prefix in ("https://api.hh.ru", "http://api.hh.ru"):
            if path.startswith(prefix):
                path = path.split(prefix, 1)[1]
                break
        if not path.startswith("/"):
            path = "/" + path
        return await self._request(
            "GET",
            path,
            params={"page": page, "per_page": per_page},
        )

    @staticmethod
    def _strip_hh_api_host(url: str) -> str:
        path = (url or "").strip()
        for prefix in ("https://api.hh.ru", "http://api.hh.ru"):
            if path.startswith(prefix):
                path = path.split(prefix, 1)[1]
                break
        if path and not path.startswith("/"):
            path = "/" + path
        return path

    async def get_negotiation(self, negotiation_id: str) -> dict:
        """Один отклик/приглашение с actions."""
        if config.MOCK_HH:
            logger.info("Return mock GET /negotiations/%s (MOCK_HH=true)", negotiation_id)
            nid = str(negotiation_id)
            return {
                "id": nid,
                "created_at": "2026-08-14T10:00:00+0300",
                "state": {"id": "response", "name": "Отклик"},
                "employer_state": {"id": "response", "name": "Неразобранные"},
                "alternate_url": f"https://hh.ru/employer/vacancyresponses/{nid}",
                "resume": {
                    "id": f"resume-{nid}",
                    "title": "Кандидат",
                    "first_name": "Иван",
                    "last_name": "Иванов",
                    "age": 30,
                    "alternate_url": f"https://hh.ru/resume/resume-{nid}",
                    "area": {"name": "Москва"},
                },
                "actions": [
                    {
                        "id": "discard",
                        "name": "Отказ",
                        "enabled": True,
                        "method": "PUT",
                        "url": f"https://api.hh.ru/negotiations/discard/{nid}",
                        "arguments": [{"id": "message", "required": False}],
                        "resulting_employer_state": {"id": "discard", "name": "Отказ"},
                    },
                    {
                        "id": "consider",
                        "name": "Подумать",
                        "enabled": True,
                        "method": "PUT",
                        "url": f"https://api.hh.ru/negotiations/consider/{nid}",
                        "resulting_employer_state": {"id": "consider", "name": "Подумать"},
                    },
                    {
                        "id": "phone_interview",
                        "name": "Телефонное интервью",
                        "enabled": True,
                        "method": "PUT",
                        "url": f"https://api.hh.ru/negotiations/phone_interview/{nid}",
                        "arguments": [{"id": "message", "required": False}],
                    },
                    {
                        "id": "interview",
                        "name": "Пригласить на собеседование",
                        "enabled": True,
                        "method": "PUT",
                        "url": f"https://api.hh.ru/negotiations/interview/{nid}",
                        "arguments": [{"id": "message", "required": False}],
                    },
                    {
                        "id": "hired",
                        "name": "Выход на работу",
                        "enabled": True,
                        "method": "PUT",
                        "url": f"https://api.hh.ru/negotiations/hired/{nid}",
                        "arguments": [],
                    },
                    {
                        "id": "offer",
                        "name": "Предложение о работе",
                        "enabled": True,
                        "method": "PUT",
                        "url": f"https://api.hh.ru/negotiations/offer/{nid}",
                        "arguments": [{"id": "message", "required": False}],
                        "resulting_employer_state": {"id": "offer", "name": "Предложение о работе"},
                    },
                ],
            }
        return await self._request("GET", f"/negotiations/{negotiation_id}")

    async def get_resume(self, resume_id: str) -> dict:
        if config.MOCK_HH:
            logger.info("Return mock GET /resumes/%s (MOCK_HH=true)", resume_id)
            data = dict(mock.resume_example)
            data["id"] = str(resume_id)
            return data
        return await self._request("GET", f"/resumes/{resume_id}")

    async def execute_negotiation_action(
        self,
        negotiation_id: str,
        action_id: Union[str, Sequence[str]],
        *,
        arguments: Optional[dict] = None,
        topic: Optional[dict] = None,
        require_arguments: Optional[Sequence[str]] = None,
    ) -> Any:
        """
        Выполнить действие HH по отклику (discard / interview / hired / ...).
        method и url берутся из topic.actions (список коллекции) или GET /negotiations/{id}.

        ``action_id`` may be a single id or an ordered list of fallbacks
        (first enabled action with a url wins).
        ``require_arguments`` — action must declare these form fields (e.g. message).
        """
        wanted = (
            [str(action_id)]
            if isinstance(action_id, str)
            else [str(a) for a in action_id if a]
        )
        if not wanted:
            raise HTTPException(400, "action_id is required")
        required = [str(x) for x in (require_arguments or ()) if x]

        if config.MOCK_HH:
            logger.info(
                "Return mock negotiation action %s on %s (MOCK_HH=true)",
                wanted[0],
                negotiation_id,
            )
            return {"status": "ok", "action_id": wanted[0], "id": str(negotiation_id)}

        resolved = topic if isinstance(topic, dict) else None
        if resolved is None:
            resolved = await self.get_negotiation(str(negotiation_id))

        def _action_args(action: dict) -> set[str]:
            return {
                a.get("id")
                for a in (action.get("arguments") or [])
                if isinstance(a, dict) and a.get("id")
            }

        def _pick_action(src: Optional[dict]) -> Optional[dict]:
            actions = src.get("actions") if isinstance(src, dict) else None
            by_id = {
                a.get("id"): a
                for a in (actions or [])
                if isinstance(a, dict) and a.get("id")
            }
            for aid in wanted:
                a = by_id.get(aid)
                if (
                    isinstance(a, dict)
                    and a.get("enabled")
                    and a.get("url")
                ):
                    if required and not all(name in _action_args(a) for name in required):
                        continue
                    return a
            return None

        action = _pick_action(resolved)
        # List payloads sometimes omit url; refresh topic once.
        if not action:
            resolved = await self.get_negotiation(str(negotiation_id))
            action = _pick_action(resolved)

        if not action:
            available = []
            for a in (resolved.get("actions") or []) if isinstance(resolved, dict) else []:
                if isinstance(a, dict) and a.get("id"):
                    available.append(
                        f"{a.get('id')}:{'on' if a.get('enabled') else 'off'}"
                    )
            tried = ", ".join(wanted)
            raise HTTPException(
                409,
                f"HH action '{tried}' unavailable for negotiation {negotiation_id}"
                + (f" (available: {', '.join(available)})" if available else " (no actions)"),
            )

        method = (action.get("method") or "PUT").upper()
        path = self._strip_hh_api_host(action["url"])
        allowed = {
            a.get("id")
            for a in (action.get("arguments") or [])
            if isinstance(a, dict) and a.get("id")
        }
        form: dict[str, str] = {}
        if arguments:
            for key, value in arguments.items():
                if value is None:
                    continue
                if allowed and key not in allowed:
                    continue
                form[str(key)] = str(value)
        return await self._request(method, path, data=form or None)

    # HH may expose employer-side discard under a different action id.
    DISCARD_ACTION_IDS = (
        "discard",
        "discard_by_employer",
        "discard_no_interaction",
    )
    CONSIDER_ACTION_IDS = (
        "consider",
        "to_consider",
    )
    OFFER_ACTION_IDS = (
        "offer",
        "make_offer",
    )
    INTERVIEW_ACTION_IDS = (
        "interview",
    )
    # Chat POST /messages is allowed only after invitation. These actions
    # accept a letter the same way discard does (form field ``message``).
    # Interview is last: it titles the letter «Собеседование» on hh.ru.
    MESSAGE_DELIVERY_ACTION_IDS = (
        "assessment",
        "phone_interview",
        "interview",
    )
    # Never use interview/phone_interview when delivering an offer letter.
    OFFER_MESSAGE_FALLBACK_ACTION_IDS = (
        "assessment",
    )
    OFFER_LETTER_HEADING = "Приглашаем вас на работу"

    async def discard_negotiation(
        self,
        negotiation_id: str,
        *,
        message: Optional[str] = None,
        topic: Optional[dict] = None,
    ) -> Any:
        """
        Отказ кандидату по отклику.
        Пробует discard → discard_by_employer → discard_no_interaction
        (у части откликов классический discard отключён).
        Предпочитает actions из списка коллекции (topic), иначе GET /negotiations/{id}.
        """
        if config.MOCK_HH:
            logger.info("Return mock discard negotiation %s (MOCK_HH=true)", negotiation_id)
            return {"status": "discarded", "id": str(negotiation_id)}

        arguments: dict[str, str] = {}
        if message is not None:
            arguments["message"] = message
        return await self.execute_negotiation_action(
            negotiation_id,
            self.DISCARD_ACTION_IDS,
            arguments=arguments or None,
            topic=topic,
        )

    async def consider_negotiation(
        self,
        negotiation_id: str,
        *,
        topic: Optional[dict] = None,
    ) -> Any:
        """Перевести отклик в HH «Подумать» (consider)."""
        if config.MOCK_HH:
            logger.info("Return mock consider negotiation %s (MOCK_HH=true)", negotiation_id)
            return {"status": "considered", "id": str(negotiation_id)}
        return await self.execute_negotiation_action(
            negotiation_id,
            self.CONSIDER_ACTION_IDS,
            topic=topic,
        )

    async def offer_negotiation(
        self,
        negotiation_id: str,
        *,
        message: Optional[str] = None,
        topic: Optional[dict] = None,
    ) -> Any:
        """Перевести отклик в HH «Предложение о работе» (offer) и передать текст."""
        letter = apply_offer_letter_heading(message) if message is not None else None
        if config.MOCK_HH:
            logger.info("Return mock offer negotiation %s (MOCK_HH=true)", negotiation_id)
            return {"status": "offered", "id": str(negotiation_id)}
        arguments: dict[str, str] = {}
        if letter is not None:
            arguments["message"] = letter
        try:
            return await self.execute_negotiation_action(
                negotiation_id,
                self.OFFER_ACTION_IDS,
                arguments=arguments or None,
                topic=topic,
            )
        except HTTPException as exc:
            if exc.status_code != 409 or not letter:
                raise
            logger.info(
                "HH offer action unavailable for %s — sending chat message instead",
                negotiation_id,
            )
            return await self.send_message_to_negotiation(
                negotiation_id,
                letter,
                fallback_action_ids=self.OFFER_MESSAGE_FALLBACK_ACTION_IDS,
            )

    async def interview_negotiation(
        self,
        negotiation_id: str,
        *,
        message: Optional[str] = None,
        topic: Optional[dict] = None,
    ) -> Any:
        """Приглашение на собеседование (HH action interview) с текстом письма."""
        text = str(message or "").strip() or None
        if config.MOCK_HH:
            logger.info("Return mock interview negotiation %s (MOCK_HH=true)", negotiation_id)
            return {"status": "interview_invited", "id": str(negotiation_id)}
        arguments: dict[str, str] = {}
        if text is not None:
            arguments["message"] = text
        try:
            return await self.execute_negotiation_action(
                negotiation_id,
                self.INTERVIEW_ACTION_IDS,
                arguments=arguments or None,
                topic=topic,
            )
        except HTTPException as exc:
            if exc.status_code != 409 or not text:
                raise
            logger.info(
                "HH interview action unavailable for %s — sending chat message instead",
                negotiation_id,
            )
            return await self.send_message_to_negotiation(
                negotiation_id,
                text,
                fallback_action_ids=self.INTERVIEW_ACTION_IDS,
            )

    async def send_message_to_negotiation(
        self,
        negotiation_id: str,
        message: str,
        *,
        fallback_action_ids: Optional[Sequence[str]] = None,
    ) -> Any:
        text = str(message or "").strip()
        if not text:
            raise HTTPException(400, "message is required")
        if config.MOCK_HH:
            logger.info("Return mock chat message for negotiation %s (MOCK_HH=true)", negotiation_id)
            return {"status": "sent", "id": str(negotiation_id)}

        topic = None
        try:
            topic = await self.get_negotiation(str(negotiation_id))
        except HTTPException as exc:
            logger.warning("HH GET negotiation %s before message failed: %s", negotiation_id, exc.detail)

        path = f"/negotiations/{negotiation_id}/messages"
        if isinstance(topic, dict) and topic.get("messages_url"):
            stripped = self._strip_hh_api_host(str(topic["messages_url"]))
            if stripped:
                path = stripped

        async def _post_chat() -> Any:
            out = await self._request("POST", path, data={"message": text})
            if out is None or isinstance(out, int):
                return {"status": "sent", "id": str(negotiation_id), "via": "chat"}
            if isinstance(out, dict):
                return {**out, "status": out.get("status") or "sent", "via": "chat"}
            return {"status": "sent", "id": str(negotiation_id), "via": "chat"}

        def _chat_blocked(exc: HTTPException) -> bool:
            if exc.status_code not in (400, 403):
                return False
            detail = str(exc.detail or "").lower()
            return exc.status_code == 403 or any(
                hint in detail
                for hint in ("no_invitation", "cannot be sent")
            )

        try:
            return await _post_chat()
        except HTTPException as chat_exc:
            if not _chat_blocked(chat_exc):
                raise
            logger.info(
                "HH chat blocked for %s (%s) — consider then retry / action with message",
                negotiation_id,
                chat_exc.detail,
            )
            try:
                await self.consider_negotiation(
                    str(negotiation_id),
                    topic=topic if isinstance(topic, dict) else None,
                )
            except HTTPException as consider_exc:
                logger.info(
                    "HH consider before message skipped for %s: %s",
                    negotiation_id,
                    consider_exc.detail,
                )
            try:
                return await _post_chat()
            except HTTPException:
                pass
            try:
                out = await self.execute_negotiation_action(
                    str(negotiation_id),
                    fallback_action_ids or self.MESSAGE_DELIVERY_ACTION_IDS,
                    arguments={"message": text},
                    topic=None,
                    require_arguments=("message",),
                )
                if out is None:
                    return {"status": "sent", "id": str(negotiation_id), "via": "action"}
                if isinstance(out, dict):
                    return {**out, "via": "action"}
                return {"status": "sent", "id": str(negotiation_id), "via": "action"}
            except HTTPException:
                raise chat_exc

    # === Вспомогательные методы ===
    async def get_dictionaries(self) -> dict:
        """Возвращает справочники HH (areas, roles и т.д.)"""
        return await self._request("GET", "/dictionaries")

    async def get_me(self) -> dict:
        """Возвращает информацию о текущем пользователе"""
        return await self._request("GET", "/me")

    async def close(self):
        """Закрывает httpx клиент (желательно вызывать при остановке сервиса)"""
        await self.client.aclose()