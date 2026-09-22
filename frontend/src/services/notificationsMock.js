/**
 * In-memory mock store for notifications (frontend-only until backend exists).
 * Persists lightly in localStorage when available.
 */

const STORAGE_KEY = "hr_platform_notifications_mock_v1";

function nowIso() {
    return new Date().toISOString();
}

function defaultSeed() {
    const t = Date.now();
    return {
        messages: [
            {
                id: 1,
                content: "Новая заявка на подбор: Логист",
                is_read: false,
                user_id: null,
                role: "hr",
                channel_id: 1,
                entity_type: "hiring_request",
                entity_id: 101,
                created_at: new Date(t - 5 * 60000).toISOString(),
            },
            {
                id: 2,
                content: "Вакансия «Водитель» опубликована на HH.ru",
                is_read: false,
                user_id: "__demo_user__",
                role: null,
                channel_id: null,
                entity_type: "vacancy",
                entity_id: 55,
                created_at: new Date(t - 35 * 60000).toISOString(),
            },
            {
                id: 3,
                content: "Кандидат Иванов прошёл тестирование",
                is_read: true,
                user_id: "__demo_user__",
                role: null,
                channel_id: 2,
                entity_type: "candidate",
                entity_id: 9,
                created_at: new Date(t - 2 * 3600000).toISOString(),
            },
            {
                id: 4,
                content: "Напоминание: дедлайн по заявке З-12 через 2 дня",
                is_read: false,
                user_id: null,
                role: "owner",
                channel_id: null,
                entity_type: "hiring_request",
                entity_id: 12,
                created_at: new Date(t - 26 * 3600000).toISOString(),
            },
        ],
        channels: [
            {
                id: 1,
                name: "Заявки на подбор",
                entity_type: "hiring_request",
                entity_id: 0,
            },
            {
                id: 2,
                name: "Кандидаты",
                entity_type: "candidate",
                entity_id: 0,
            },
            {
                id: 3,
                name: "Вакансии",
                entity_type: "vacancy",
                entity_id: 0,
            },
        ],
        settings: [
            { id: 1, channel_id: 1, is_send_push_message: true },
            { id: 2, channel_id: 2, is_send_push_message: true },
            { id: 3, channel_id: 3, is_send_push_message: false },
        ],
        nextId: 5,
        nextSettingId: 4,
    };
}

function loadState() {
    try {
        if (typeof localStorage !== "undefined") {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed?.messages && parsed?.channels) return parsed;
            }
        }
    } catch {
        /* ignore */
    }
    return defaultSeed();
}

function saveState(state) {
    try {
        if (typeof localStorage !== "undefined") {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }
    } catch {
        /* ignore */
    }
}

let state = loadState();
const listeners = new Set();

export function __resetNotificationsMock(seed) {
    state = seed || defaultSeed();
    saveState(state);
}

export function __getNotificationsMockState() {
    return state;
}

function emit(payload) {
    listeners.forEach((cb) => {
        try {
            cb(payload);
        } catch {
            /* ignore */
        }
    });
}

export function subscribeMockNotifications(callback) {
    listeners.add(callback);
    return () => listeners.delete(callback);
}

export function pushMockNotification(partial = {}) {
    const msg = {
        id: state.nextId++,
        content: partial.content || "Тестовое уведомление",
        is_read: false,
        user_id: partial.user_id ?? null,
        role: partial.role ?? null,
        channel_id: partial.channel_id ?? null,
        entity_type: partial.entity_type ?? null,
        entity_id: partial.entity_id ?? null,
        created_at: partial.created_at || nowIso(),
        type: "notification",
        is_send: true,
    };
    state.messages = [msg, ...state.messages];
    saveState(state);
    emit(msg);
    return msg;
}

function matchesParams(msg, params = {}) {
    if (params.user_id != null) {
        if (msg.user_id === "__demo_user__") return true;
        return String(msg.user_id) === String(params.user_id);
    }
    if (params.role != null) {
        return String(msg.role) === String(params.role);
    }
    if (params.role_id != null) {
        return Number(msg.role_id) === Number(params.role_id);
    }
    if (params.channel_id != null) {
        return Number(msg.channel_id) === Number(params.channel_id);
    }
    return true;
}

export async function mockFetchUnreadCount() {
    const count = state.messages.filter((m) => !m.is_read).length;
    return { count };
}

export async function mockFetchMessages(params = {}) {
    return state.messages
        .filter((m) => matchesParams(m, params))
        .slice()
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

export async function mockMarkMessagesAsRead(params = {}) {
    let marked = 0;
    state.messages = state.messages.map((m) => {
        if (!matchesParams(m, params) || m.is_read) return m;
        marked += 1;
        return { ...m, is_read: true };
    });
    saveState(state);
    return { marked };
}

export async function mockMarkMessageAsRead(messageId) {
    const id = Number(messageId);
    let updated = null;
    state.messages = state.messages.map((message) => {
        if (Number(message.id) !== id) return message;
        updated = { ...message, is_read: true };
        return updated;
    });
    if (!updated) throw new Error("Уведомление не найдено");
    saveState(state);
    return updated;
}

export async function mockFetchUserChannels() {
    return state.channels.slice();
}

export async function mockFetchUserSettings() {
    return state.settings.slice();
}

export async function mockCreateChannelSettings(body) {
    const row = {
        id: state.nextSettingId++,
        channel_id: Number(body.channel_id),
        is_send_push_message: !!body.is_send_push_message,
    };
    state.settings = [...state.settings, row];
    saveState(state);
    return row;
}

export async function mockUpdateChannelSettings(id, body) {
    const sid = Number(id);
    state.settings = state.settings.map((s) =>
        Number(s.id) === sid
            ? { ...s, is_send_push_message: !!body.is_send_push_message }
            : s
    );
    saveState(state);
    return state.settings.find((s) => Number(s.id) === sid) || null;
}
