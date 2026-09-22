import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useNotifications } from "../../hooks/useNotifications";
import { useWebPush } from "../../hooks/useWebPush";
import NotificationRealtime from "./NotificationRealtime";
import {
    formatRelativeTime,
    hasMessageFilterParams,
} from "../../utils/notificationLogic";
import {
    notificationIsNavigable,
    notificationRoutePath,
} from "../../utils/notificationWsLogic";

function BellIcon({ className = "w-5 h-5" }) {
    return (
        <svg
            className={className}
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
            <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
    );
}

/**
 * Header bell + dropdown (ERP NotificationButton UX, React).
 */
export default function NotificationBell() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const rootRef = useRef(null);
    const closePanelRef = useRef(() => {});
    const n = useNotifications({ user, enabled: !!user?.id });
    const push = useWebPush({ enabled: !!user?.id });
    closePanelRef.current = n.closePanel;

    useEffect(() => {
        if (!n.isOpen) return undefined;
        const onDoc = (e) => {
            if (rootRef.current && !rootRef.current.contains(e.target)) {
                closePanelRef.current();
            }
        };
        document.addEventListener("mousedown", onDoc);
        return () => document.removeEventListener("mousedown", onDoc);
    }, [n.isOpen]);

    if (!user?.id) return null;

    const bellAria =
        n.unreadCount > 0
            ? `Уведомления, ${n.unreadCount} непрочитанных`
            : "Уведомления";

    const onMessageClick = (msg) => {
        if (!notificationIsNavigable(msg)) return;
        const path = notificationRoutePath(msg);
        if (path) {
            n.closePanel();
            navigate(path);
        }
    };

    return (
        <div className="relative" ref={rootRef}>
            <NotificationRealtime
                enabled={!!user?.id}
                userId={user?.erp_user_id || user?.id}
                roleId={user?.role_id}
                onIncoming={() => n.refreshUnread()}
            />

            <button
                type="button"
                className="relative p-2.5 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm transition-colors"
                aria-expanded={n.isOpen ? "true" : "false"}
                aria-label={bellAria}
                onClick={(e) => {
                    e.stopPropagation();
                    n.togglePanel();
                }}
            >
                <BellIcon />
                {n.badgeText ? (
                    <span className="absolute -top-1 -right-1 min-w-[1.25rem] h-5 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center leading-none">
                        {n.badgeText}
                    </span>
                ) : null}
            </button>

            {n.isOpen && (
                <div
                    className="absolute right-0 mt-2 w-[360px] max-h-[480px] bg-white rounded-2xl shadow-xl border border-slate-200/80 z-50 flex flex-col overflow-hidden"
                    role="dialog"
                    aria-label="Уведомления"
                >
                    <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
                        <h3 className="flex-1 text-sm font-bold text-slate-900 truncate">
                            {n.panelTitle}
                        </h3>
                    </div>

                    <div className="flex-1 overflow-y-auto p-2">
                        {!hasMessageFilterParams(n.messagesParams) && (
                            <p className="px-3 py-6 text-sm text-slate-400 text-center">
                                Нет данных пользователя
                            </p>
                        )}
                        {hasMessageFilterParams(n.messagesParams) && n.messagesPending && (
                            <p className="px-3 py-6 text-sm text-slate-400 text-center">Загрузка…</p>
                        )}
                        {hasMessageFilterParams(n.messagesParams) && n.messagesError && (
                            <p className="px-3 py-6 text-sm text-red-600 text-center">
                                Не удалось загрузить уведомления
                            </p>
                        )}
                        {hasMessageFilterParams(n.messagesParams) &&
                            !n.messagesPending &&
                            !n.messagesError &&
                            n.messages.length === 0 && (
                                <p className="px-3 py-6 text-sm text-slate-400 text-center">
                                    Нет уведомлений
                                </p>
                            )}
                        {n.messages.length > 0 && (
                            <ul className="space-y-1">
                                {n.messages.map((msg) => {
                                    const link = notificationIsNavigable(msg);
                                    return (
                                        <li key={msg.id}>
                                            <button
                                                type="button"
                                                disabled={!link}
                                                onClick={() => onMessageClick(msg)}
                                                className={`w-full text-left px-3 py-2.5 rounded-xl border-l-4 transition-colors ${
                                                    !msg.is_read
                                                        ? "border-indigo-500 bg-indigo-50/60"
                                                        : "border-transparent hover:bg-slate-50"
                                                } ${link ? "cursor-pointer" : "cursor-default"}`}
                                            >
                                                <span className="block text-sm text-slate-800 leading-snug">
                                                    {msg.content}
                                                </span>
                                                <span className="block text-[11px] text-slate-400 mt-1">
                                                    {formatRelativeTime(msg.created_at)}
                                                </span>
                                            </button>
                                        </li>
                                    );
                                })}
                            </ul>
                        )}
                    </div>
                    <div className="p-2 border-t border-slate-100 bg-slate-50/70">
                        {push.supported && push.permission !== "granted" ? (
                            <button
                                type="button"
                                onClick={() => push.ensurePush()}
                                className="w-full px-3 py-2 text-sm font-semibold text-indigo-700 hover:bg-indigo-50 rounded-xl transition-colors"
                            >
                                Включить системные уведомления
                            </button>
                        ) : null}
                        <button
                            type="button"
                            onClick={() => {
                                n.closePanel();
                                navigate("/notifications");
                            }}
                            className="w-full px-3 py-2 text-sm font-semibold text-yellow-800 hover:bg-yellow-50 rounded-xl transition-colors"
                        >
                            Все уведомления
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
