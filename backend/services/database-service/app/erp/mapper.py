"""Map ERP /api/v2/users/ payload → HR panel user fields."""
from __future__ import annotations

from typing import Any, Optional

from app.config import ERP_DEFAULT_ROLE, ERP_ROLE_MAP, ERP_SKIP_UNMAPPED_ROLES
from app.db.v1.enums import AdminRoles
from app.app_logging import logger

ALLOWED_ROLES = {role.value for role in AdminRoles}

# Default ERP display-name → AdminRoles (also overridable via ERP_ROLE_MAP env).
DEFAULT_ERP_ROLE_ALIASES = {
    "superadmin": AdminRoles.superadmin.value,
    "админ": AdminRoles.admin.value,
    "менеджер": AdminRoles.manager.value,
    "руководитель": AdminRoles.leader.value,
    "руководитель отдела": AdminRoles.dept_leader.value,
    "старший менеджер": AdminRoles.senior_manager.value,
    # Native / English aliases kept for sync flexibility
    "hr": AdminRoles.hr.value,
    "кадры": AdminRoles.hr.value,
    "кадровик": AdminRoles.hr.value,
    "owner": AdminRoles.owner.value,
    "lead": AdminRoles.lead.value,
    "art": AdminRoles.art.value,
    "dev": AdminRoles.dev.value,
    "admin": AdminRoles.admin.value,
    "manager": AdminRoles.manager.value,
    "leader": AdminRoles.leader.value,
    "dept_leader": AdminRoles.dept_leader.value,
    "senior_manager": AdminRoles.senior_manager.value,
    "разработчик": AdminRoles.dev.value,
}


def _erp_role_name(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        name = raw.get("name")
        return str(name).strip() if name else None
    return str(raw).strip() or None


def map_role(erp_role: Any) -> Optional[str]:
    name = _erp_role_name(erp_role)
    if not name:
        role = ERP_DEFAULT_ROLE
    else:
        key = name.lower()
        if key in ALLOWED_ROLES:
            role = key
        elif key in ERP_ROLE_MAP:
            role = ERP_ROLE_MAP[key]
        elif key in DEFAULT_ERP_ROLE_ALIASES:
            role = DEFAULT_ERP_ROLE_ALIASES[key]
        else:
            if ERP_SKIP_UNMAPPED_ROLES:
                logger.info(f"Skip user with unmapped ERP role: {name}")
                return None
            role = ERP_DEFAULT_ROLE

    role = (role or ERP_DEFAULT_ROLE).lower()
    if role not in ALLOWED_ROLES:
        logger.warning(f"Invalid mapped role '{role}', falling back to '{ERP_DEFAULT_ROLE}'")
        role = ERP_DEFAULT_ROLE if ERP_DEFAULT_ROLE in ALLOWED_ROLES else AdminRoles.dev.value
    return role


def derive_username(email: Optional[str], erp_id: str) -> str:
    if email and "@" in email:
        return email.strip().lower()[:100]
    return f"erp_{erp_id.replace('-', '')[:40]}"


def map_erp_user(raw: dict) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    if raw.get("is_active") is False:
        return None

    erp_id = raw.get("id")
    if not erp_id:
        return None
    erp_id = str(erp_id)[:36]

    role = map_role(raw.get("role"))
    if not role:
        return None

    email = raw.get("email")
    username = derive_username(str(email).strip() if email else None, erp_id)
    full_name = raw.get("name")
    if full_name:
        full_name = str(full_name).strip()[:200] or None

    role_label = _erp_role_name(raw.get("role"))
    mapped = {
        "erp_user_id": erp_id,
        "username": username,
        "full_name": full_name,
        "role": role,
        "department": role_label,
        "position": role_label,
    }
    if "date_hired" in raw:
        mapped["date_hired"] = raw.get("date_hired")
    return mapped


def map_erp_users(raw_users: list) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for raw in raw_users or []:
        item = map_erp_user(raw)
        if not item:
            continue
        if item["erp_user_id"] in seen:
            continue
        seen.add(item["erp_user_id"])
        out.append(item)
    return out


def normalize_tg_username(value: Optional[str]) -> Optional[str]:
    """Align with ERP: always store as @username."""
    username = (value or "").strip()
    if not username:
        return None
    return "@" + username.lstrip("@")


def map_erp_directory_user(raw: dict) -> Optional[dict]:
    """Map active ERP account for directory search (no HR role filter)."""
    if not isinstance(raw, dict):
        return None
    if raw.get("is_active") is False:
        return None

    erp_id = raw.get("id")
    if not erp_id:
        return None
    erp_id = str(erp_id)[:36]

    full_name = raw.get("name") or raw.get("full_name")
    if full_name:
        full_name = str(full_name).strip()[:200] or None

    tg_username = normalize_tg_username(
        raw.get("tg_username") or raw.get("telegram_username") or raw.get("telegram")
    )

    if not full_name and not tg_username:
        return None

    email = raw.get("email")
    username = derive_username(str(email).strip() if email else None, erp_id)
    return {
        "erp_user_id": erp_id,
        "full_name": full_name,
        "username": username,
        "tg_username": tg_username,
    }


def search_erp_directory_users(
    raw_users: list,
    *,
    query: str,
    limit: int = 15,
    by: str = "name",
) -> list[dict]:
    """Filter ERP users by FIO or Telegram username (case-insensitive)."""
    mode = (by or "name").strip().lower()
    if mode not in ("name", "telegram"):
        mode = "name"

    q = (query or "").strip().lower()
    if not q:
        return []
    if mode == "telegram":
        q = q.lstrip("@")
        if not q:
            return []

    matched: list[tuple[int, str, dict]] = []
    seen: set[str] = set()
    for raw in raw_users or []:
        item = map_erp_directory_user(raw)
        if not item:
            continue
        erp_id = item["erp_user_id"]
        if erp_id in seen:
            continue
        seen.add(erp_id)

        if mode == "telegram":
            tg = (item.get("tg_username") or "").lower().lstrip("@")
            if not tg or q not in tg:
                continue
            rank = 0 if tg.startswith(q) else 1
            sort_key = tg
        else:
            name = (item.get("full_name") or "").lower()
            if not name:
                continue
            username = (item.get("username") or "").lower()
            if q not in name and q not in username:
                continue
            # Prefer prefix matches, then substring.
            rank = 0 if name.startswith(q) else (1 if q in name else 2)
            sort_key = name

        matched.append((rank, sort_key, item))

    matched.sort(key=lambda pair: (pair[0], pair[1]))
    return [item for _, _, item in matched[: max(1, limit)]]


def find_erp_user_id_by_telegram(
    raw_users: list,
    telegram_user: Optional[str],
) -> Optional[str]:
    """Exact match of tg_username → ERP user UUID (recipient of the TG message)."""
    target = normalize_tg_username(telegram_user)
    if not target:
        return None
    bare = target.lower().lstrip("@")

    for raw in raw_users or []:
        item = map_erp_directory_user(raw)
        if not item:
            continue
        tg = (item.get("tg_username") or "").lower().lstrip("@")
        if tg and tg == bare:
            return item["erp_user_id"]
    return None
