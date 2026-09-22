import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import MainLayout from "../layout/MainLayout";
import { useAuth } from "../context/AuthContext";
import { useAlertContext } from "../context/AlertContext";
import {
    createChannelSettings,
    fetchMessages,
    fetchUnreadCount,
    fetchUserChannels,
    fetchUserSettings,
    markMessageAsRead,
    markMessagesAsRead,
    updateChannelSettings,
} from "../services/notificationsApi";
import {
    buildChannelMessagesParams,
    buildPersonalMessagesParams,
    findSettingsForChannel,
    formatRelativeTime,
    formatUnreadBadge,
    roleSectionTitle,
} from "../utils/notificationLogic";
import {
    notificationIsNavigable,
    notificationRoutePath,
} from "../utils/notificationWsLogic";

const SECTIONS = Object.freeze({ PERSONAL: "personal", ROLE: "role", CHANNELS: "channels" });

function validSection(value) {
    return Object.values(SECTIONS).includes(value) ? value : SECTIONS.PERSONAL;
}

function MessageList({ messages, pending, error, onSelect }) {
    if (pending) return <p className="py-14 text-center text-sm text-slate-400">Загрузка…</p>;
    if (error) return <p className="py-14 text-center text-sm text-red-600">Не удалось загрузить уведомления</p>;
    if (!messages.length) return <p className="py-14 text-center text-sm text-slate-400">Нет уведомлений</p>;

    return (
        <ul className="divide-y divide-slate-100">
            {messages.map((message) => {
                const unread = !message.is_read;
                const clickable = unread || notificationIsNavigable(message);
                return (
                    <li key={message.id}>
                        <button
                            type="button"
                            disabled={!clickable}
                            onClick={() => onSelect(message)}
                            aria-label={unread ? `${message.content || "Уведомление"}, непрочитано` : undefined}
                            className={`w-full flex items-start gap-3 px-5 py-4 text-left transition-colors ${
                                unread ? "bg-indigo-50/80" : "bg-white"
                            } ${clickable ? "hover:bg-slate-50 cursor-pointer" : "cursor-default"}`}
                        >
                            <span
                                className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${unread ? "bg-indigo-600" : "bg-transparent"}`}
                                aria-hidden="true"
                            />
                            <span className="min-w-0 flex-1">
                                <span className={`block text-sm leading-relaxed text-slate-800 whitespace-pre-wrap break-words ${unread ? "font-semibold" : ""}`}>
                                    {message.content || "Уведомление"}
                                </span>
                                <span className="block mt-1.5 text-xs text-slate-400">
                                    {formatRelativeTime(message.created_at)}
                                </span>
                            </span>
                            {notificationIsNavigable(message) ? (
                                <span className="mt-1 text-slate-300" aria-hidden="true">›</span>
                            ) : null}
                        </button>
                    </li>
                );
            })}
        </ul>
    );
}

export default function NotificationsPage() {
    const { user } = useAuth();
    const { showAlert } = useAlertContext();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const section = validSection(searchParams.get("section"));
    const channelId = Number(searchParams.get("channelId")) || null;
    const roleId = Number(user?.role_id ?? user?.role?.id) || null;

    const [unreadCount, setUnreadCount] = useState(0);
    const [messages, setMessages] = useState([]);
    const [channels, setChannels] = useState([]);
    const [settings, setSettings] = useState([]);
    const [pending, setPending] = useState(true);
    const [error, setError] = useState(false);
    const [togglePending, setTogglePending] = useState(false);

    const selectedChannel = channels.find((channel) => Number(channel.id) === channelId) || null;
    const messageParams = useMemo(() => {
        if (section === SECTIONS.PERSONAL) return buildPersonalMessagesParams(user?.erp_user_id || user?.id);
        if (section === SECTIONS.ROLE) {
            return roleId ? { role_id: roleId, role: String(user?.role || "") } : null;
        }
        if (channelId) return buildChannelMessagesParams(channelId);
        return null;
    }, [channelId, roleId, section, user?.erp_user_id, user?.id, user?.role]);

    const refreshUnread = useCallback(async () => {
        try {
            setUnreadCount(Number(await fetchUnreadCount()) || 0);
        } catch {
            // The page remains usable when the counter endpoint is temporarily unavailable.
        }
    }, []);

    const load = useCallback(async (signal) => {
        setPending(true);
        setError(false);
        try {
            if (section === SECTIONS.CHANNELS && !channelId) {
                const [nextChannels, nextSettings] = await Promise.all([
                    fetchUserChannels({}, { signal }),
                    fetchUserSettings({ signal }),
                ]);
                setChannels(Array.isArray(nextChannels) ? nextChannels : []);
                setSettings(Array.isArray(nextSettings) ? nextSettings : []);
                setMessages([]);
            } else if (messageParams) {
                const list = await fetchMessages(messageParams, { signal });
                setMessages(Array.isArray(list) ? list : []);
                if (channelId) {
                    const [nextChannels, nextSettings] = await Promise.all([
                        fetchUserChannels({}, { signal }),
                        fetchUserSettings({ signal }),
                    ]);
                    setChannels(Array.isArray(nextChannels) ? nextChannels : []);
                    setSettings(Array.isArray(nextSettings) ? nextSettings : []);
                }
            } else {
                setMessages([]);
            }
        } catch (err) {
            if (err?.name !== "AbortError") setError(true);
        } finally {
            if (!signal?.aborted) setPending(false);
        }
    }, [channelId, messageParams, section]);

    useEffect(() => {
        const controller = new AbortController();
        load(controller.signal);
        refreshUnread();
        return () => controller.abort();
    }, [load, refreshUnread]);

    const setSection = (next) => setSearchParams({ section: next }, { replace: true });
    const openChannel = (channel) => setSearchParams({ section: SECTIONS.CHANNELS, channelId: String(channel.id) });

    const onMessageClick = async (message) => {
        if (!message.is_read) {
            setMessages((list) => list.map((item) => Number(item.id) === Number(message.id) ? { ...item, is_read: true } : item));
            try {
                await markMessageAsRead(message.id);
                refreshUnread();
            } catch (err) {
                setMessages((list) => list.map((item) => Number(item.id) === Number(message.id) ? { ...item, is_read: false } : item));
                showAlert(`Не удалось отметить уведомление: ${err.message || err}`, "error");
                return;
            }
        }
        const target = notificationRoutePath(message);
        if (target) navigate(target);
    };

    const markAllRead = async () => {
        if (!messageParams || !messages.some((message) => !message.is_read)) return;
        try {
            await markMessagesAsRead(messageParams);
            setMessages((list) => list.map((message) => ({ ...message, is_read: true })));
            refreshUnread();
        } catch (err) {
            showAlert(`Не удалось отметить уведомления: ${err.message || err}`, "error");
        }
    };

    const toggleChannel = async (channel, enabled) => {
        const existing = findSettingsForChannel(settings, channel.id);
        setTogglePending(true);
        try {
            const saved = existing?.id
                ? await updateChannelSettings(existing.id, { is_send_push_message: enabled })
                : await createChannelSettings({ channel_id: Number(channel.id), is_send_push_message: enabled });
            setSettings((list) => existing?.id
                ? list.map((item) => Number(item.id) === Number(existing.id) ? saved : item)
                : [...list, saved]);
        } catch (err) {
            showAlert(`Не удалось изменить настройки канала: ${err.message || err}`, "error");
        } finally {
            setTogglePending(false);
        }
    };

    const panelTitle = section === SECTIONS.PERSONAL
        ? "Личные уведомления"
        : section === SECTIONS.ROLE
            ? roleSectionTitle(user?.role)
            : selectedChannel?.name || (channelId ? `Канал #${channelId}` : "Каналы");

    return (
        <MainLayout>
            <div className="max-w-4xl mx-auto pb-10">
                <div className="mb-6">
                    <div className="flex flex-wrap items-baseline gap-3">
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Уведомления</h1>
                        {formatUnreadBadge(unreadCount) ? (
                            <span className="text-sm font-semibold text-red-600">{formatUnreadBadge(unreadCount)} непрочитанных</span>
                        ) : null}
                    </div>
                    <p className="mt-2 text-sm text-slate-500">
                        Полный список сообщений по разделам. Быстрый просмотр остаётся в колокольчике в шапке.
                    </p>
                </div>

                <div className="flex flex-wrap gap-2 mb-4" role="tablist" aria-label="Разделы уведомлений">
                    {[
                        [SECTIONS.PERSONAL, "Личные"],
                        [SECTIONS.ROLE, roleSectionTitle(user?.role)],
                        [SECTIONS.CHANNELS, "Каналы"],
                    ].map(([id, label]) => (
                        <button
                            key={id}
                            type="button"
                            role="tab"
                            aria-selected={section === id}
                            onClick={() => setSection(id)}
                            className={`px-4 py-2 rounded-full border text-sm font-medium transition-colors ${
                                section === id
                                    ? "bg-indigo-600 border-indigo-600 text-white"
                                    : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                            }`}
                        >
                            {label}
                        </button>
                    ))}
                </div>

                <section className="bg-white border border-slate-200/80 rounded-2xl shadow-sm overflow-hidden">
                    <div className="min-h-[58px] flex items-center gap-3 px-5 py-3 border-b border-slate-100 bg-slate-50/70">
                        {channelId ? (
                            <button type="button" onClick={() => setSection(SECTIONS.CHANNELS)} className="text-sm font-semibold text-indigo-700 hover:text-indigo-800">
                                ← К каналам
                            </button>
                        ) : null}
                        <h2 className="flex-1 text-base font-bold text-slate-900">{panelTitle}</h2>
                        {messageParams && messages.some((message) => !message.is_read) ? (
                            <button type="button" onClick={markAllRead} className="text-xs font-semibold text-slate-500 hover:text-slate-800">
                                Прочитать все
                            </button>
                        ) : null}
                        {channelId && selectedChannel ? (
                            <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    disabled={togglePending}
                                    checked={findSettingsForChannel(settings, selectedChannel.id)?.is_send_push_message !== false}
                                    onChange={(event) => toggleChannel(selectedChannel, event.target.checked)}
                                    className="accent-yellow-500"
                                />
                                уведомления
                            </label>
                        ) : null}
                    </div>

                    {section === SECTIONS.CHANNELS && !channelId ? (
                        pending ? <p className="py-14 text-center text-sm text-slate-400">Загрузка каналов…</p>
                            : error ? <p className="py-14 text-center text-sm text-red-600">Не удалось загрузить каналы</p>
                                : channels.length ? (
                                    <ul className="divide-y divide-slate-100">
                                        {channels.map((channel) => (
                                            <li key={channel.id}>
                                                <button type="button" onClick={() => openChannel(channel)} className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-slate-50 transition-colors">
                                                    <span className="flex-1 text-sm font-medium text-slate-800">{channel.name || `Канал #${channel.id}`}</span>
                                                    {Number(channel.unread_count) > 0 ? (
                                                        <span className="min-w-5 h-5 px-1.5 rounded-full bg-red-500 text-white text-[11px] font-bold flex items-center justify-center">
                                                            {formatUnreadBadge(channel.unread_count)}
                                                        </span>
                                                    ) : null}
                                                    <span className="text-slate-300" aria-hidden="true">›</span>
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                ) : <p className="py-14 text-center text-sm text-slate-400">Нет каналов</p>
                    ) : section === SECTIONS.ROLE && !roleId ? (
                        <p className="py-14 px-5 text-center text-sm text-slate-400">Для пользователя не указан идентификатор роли</p>
                    ) : (
                        <MessageList messages={messages} pending={pending} error={error} onSelect={onMessageClick} />
                    )}
                </section>
            </div>
        </MainLayout>
    );
}
