/**
 * Pure notification list/mark-read helpers (ported from frontend-erp, HR-adapted).
 */

export const NOTIFICATION_VIEWS = Object.freeze({
    MENU: "menu",
    PERSONAL: "personal",
    ROLE: "role",
    CHANNELS: "channels",
    CHANNEL: "channel",
});

const ROLE_LABELS = {
    owner: "Собственник",
    hr: "HR",
    lead: "Руководитель",
    art: "ART",
    dev: "Dev",
};

export function formatRelativeTime(isoOrDate, now = Date.now()) {
    if (!isoOrDate) return "";
    const ts = typeof isoOrDate === "number" ? isoOrDate : new Date(isoOrDate).getTime();
    if (!Number.isFinite(ts)) return "";
    const diff = Math.max(0, now - ts);
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "только что";
    if (minutes < 60) return `${minutes} мин назад`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ч назад`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} дн назад`;
    return new Date(ts).toLocaleDateString("ru-RU");
}

export function roleSectionTitle(roleNameOrCode) {
    const raw = (roleNameOrCode || "").trim();
    if (!raw) return "Уведомления для роли";
    const label = ROLE_LABELS[raw] || raw;
    return `Уведомления: ${label}`;
}

export function formatUnreadBadge(count) {
    const n = Number(count) || 0;
    if (n <= 0) return "";
    if (n > 99) return "99+";
    return String(n);
}

/** @returns {{ user_id: string } | null} */
export function buildPersonalMessagesParams(userId) {
    if (userId == null || userId === "") return null;
    return { user_id: String(userId) };
}

/**
 * HR roles are strings (hr|owner|lead|…).
 * @returns {{ role: string } | null}
 */
export function buildRoleMessagesParams(role) {
    if (role == null || role === "") return null;
    const r = String(role).trim();
    if (!r) return null;
    return { role: r };
}

/** @returns {{ channel_id: number } | null} */
export function buildChannelMessagesParams(channelId) {
    const id = Number(channelId);
    if (!Number.isFinite(id) || id <= 0) return null;
    return { channel_id: id };
}

export function hasMessageFilterParams(params) {
    return !!params && typeof params === "object" && Object.keys(params).length > 0;
}

export function findSettingsForChannel(settingsList, channelId) {
    const id = Number(channelId);
    if (!Array.isArray(settingsList) || !Number.isFinite(id)) return null;
    return settingsList.find((s) => Number(s.channel_id) === id) || null;
}

export function parseUnreadCountPayload(data) {
    if (data == null) return 0;
    if (typeof data === "number") return data;
    if (typeof data.count === "number") return data.count;
    return Number(data.count) || 0;
}

export function parseMarkReadPayload(data) {
    if (data == null) return 0;
    if (typeof data === "number") return data;
    if (typeof data.marked === "number") return data.marked;
    return Number(data.marked) || 0;
}

export function viewMarksMessagesAsRead(view) {
    return (
        view === NOTIFICATION_VIEWS.PERSONAL ||
        view === NOTIFICATION_VIEWS.ROLE ||
        view === NOTIFICATION_VIEWS.CHANNEL
    );
}

export function shouldMarkMessagesAsRead(enabled, params, view) {
    return !!enabled && viewMarksMessagesAsRead(view) && hasMessageFilterParams(params);
}

/**
 * Load list after mark-read (mark failure must not block list).
 */
export async function loadMessagesWithMarkRead({
    params,
    view,
    markRead,
    fetchList,
    signal,
}) {
    let marked = false;
    if (shouldMarkMessagesAsRead(true, params, view)) {
        try {
            await markRead(params, { signal });
            marked = true;
        } catch (err) {
            if (
                err?.code === "ERR_CANCELED" ||
                err?.name === "CanceledError" ||
                err?.name === "AbortError"
            ) {
                throw err;
            }
        }
    }
    const raw = await fetchList(params, { signal });
    const list = Array.isArray(raw) ? raw : [];
    if (!marked) return { list, marked };
    return {
        list: list.map((m) => (m?.is_read ? m : { ...m, is_read: true })),
        marked,
    };
}
