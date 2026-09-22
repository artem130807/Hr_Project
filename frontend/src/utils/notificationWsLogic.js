/**
 * Pure realtime/notification payload helpers (ported from frontend-erp, HR routes).
 */

export function buildNotificationsWsURL(baseURL, accessToken, { protocol, host } = {}) {
    const token = (accessToken || "").trim();
    if (!token) return null;

    const proto =
        protocol ||
        (typeof window !== "undefined" && window.location?.protocol === "https:" ? "wss:" : "ws:");
    const h = host || (typeof window !== "undefined" ? window.location.host : "localhost");

    let path = (baseURL || "/notifications").replace(/\/$/, "");
    if (/^https?:\/\//i.test(path)) {
        const u = new URL(path);
        const wsProto = u.protocol === "https:" ? "wss:" : "ws:";
        return `${wsProto}//${u.host}/api/ws?token=${encodeURIComponent(token)}`;
    }
    return `${proto}//${h}${path}/api/ws?token=${encodeURIComponent(token)}`;
}

export function parseNotificationPayload(raw) {
    let data = raw;
    if (typeof raw === "string") {
        try {
            data = JSON.parse(raw);
        } catch {
            return null;
        }
    }
    if (!data || typeof data !== "object") return null;
    if (data.type && data.type !== "notification") return null;
    if (!Object.prototype.hasOwnProperty.call(data, "content")) return null;
    const entityIdRaw = data.entity_id;
    const entityId =
        entityIdRaw == null || entityIdRaw === "" ? null : Number(entityIdRaw);
    return {
        type: data.type || "notification",
        id: data.id,
        content: String(data.content ?? ""),
        is_read: !!data.is_read,
        is_send: !!data.is_send,
        user_id: data.user_id ?? null,
        role: data.role ?? null,
        role_id: data.role_id ?? null,
        channel_id: data.channel_id ?? null,
        entity_type: data.entity_type ? String(data.entity_type).toLowerCase() : null,
        entity_id: Number.isFinite(entityId) && entityId > 0 ? entityId : null,
        url: data.url ? String(data.url) : null,
        created_at: data.created_at || null,
    };
}

export function notificationToastMessage(payload) {
    if (!payload) return "";
    const text = (payload.content || "").trim();
    if (!text) return "Новое уведомление";
    return text.length > 180 ? `${text.slice(0, 177)}…` : text;
}

export function notificationKind(payload) {
    if (!payload) return "unknown";
    if (payload.channel_id != null) return "channel";
    if (payload.role != null || payload.role_id != null) return "role";
    if (payload.user_id != null) return "personal";
    return "unknown";
}

/**
 * True only for personal notifications addressed to this user.
 */
export function notificationIsPersonalForUser(payload, userId) {
    if (!payload || userId == null || userId === "") return false;
    if (payload.user_id == null || payload.user_id === "") return false;
    return String(payload.user_id) === String(userId);
}

/** The message-service authorizes the socket; this guard prevents stale/wrong-target UI events. */
export function notificationIsVisibleForUser(payload, userId, roleId) {
    if (!payload) return false;
    if (payload.channel_id != null) return true;
    if (payload.user_id != null) return notificationIsPersonalForUser(payload, userId);
    if (payload.role_id != null) {
        // Older HR sessions may not yet contain role_id; the authenticated WS hub
        // remains the source of truth in that case.
        if (roleId == null || roleId === "") return true;
        return String(payload.role_id) === String(roleId);
    }
    return payload.role != null;
}

/**
 * React Router path for HR entity deep-links.
 * @returns {string | null}
 */
export function notificationRoutePath(payload) {
    if (!payload) return null;
    const type = (payload.entity_type || "").toLowerCase();
    const id = Number(payload.entity_id);
    if (!type || !Number.isFinite(id) || id <= 0) return null;

    const routeByEntity = {
        vacancy: "/vacancies",
        hiring_request: "/requests",
        candidate: "/candidates",
        employee: "/employees",
        event: "/events",
        test: "/tests",
    };
    return routeByEntity[type] || null;
}

export function notificationIsNavigable(payload) {
    return notificationRoutePath(payload) != null;
}
