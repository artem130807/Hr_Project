import { useCallback, useEffect, useRef, useState } from "react";
import {
    fetchMessages,
    fetchUnreadCount,
    markMessagesAsRead,
} from "../services/notificationsApi";
import {
    NOTIFICATION_VIEWS,
    buildPersonalMessagesParams,
    formatUnreadBadge,
    hasMessageFilterParams,
    loadMessagesWithMarkRead,
} from "../utils/notificationLogic";

const UNREAD_POLL_MS = 30_000;

/**
 * Inbox state: unread badge polling + panel navigation/lists (ERP NotificationButton pattern).
 */
export function useNotifications({ user, enabled = true }) {
    const [isOpen, setIsOpen] = useState(false);
    const [view] = useState(NOTIFICATION_VIEWS.PERSONAL);

    const [unreadCount, setUnreadCount] = useState(0);
    const [messages, setMessages] = useState([]);
    const [messagesPending, setMessagesPending] = useState(false);
    const [messagesError, setMessagesError] = useState(false);

    const abortRef = useRef(null);
    const isAuthenticated = enabled && !!user?.id;

    const refreshUnread = useCallback(async () => {
        if (!isAuthenticated) {
            setUnreadCount(0);
            return;
        }
        try {
            const n = await fetchUnreadCount();
            setUnreadCount(Number(n) || 0);
        } catch {
            /* keep last */
        }
    }, [isAuthenticated]);

    useEffect(() => {
        refreshUnread();
        if (!isAuthenticated) return undefined;
        const id = setInterval(refreshUnread, UNREAD_POLL_MS);
        const onFocus = () => refreshUnread();
        window.addEventListener("focus", onFocus);
        return () => {
            clearInterval(id);
            window.removeEventListener("focus", onFocus);
        };
    }, [isAuthenticated, refreshUnread]);

    const messagesParams = buildPersonalMessagesParams(user?.erp_user_id || user?.id);
    const roleId = Number(user?.role_id);
    const roleParams = Number.isFinite(roleId) && roleId > 0 ? { role_id: roleId } : null;
    const messageParamSets = [messagesParams, roleParams].filter(hasMessageFilterParams);

    const messagesParamsKey = JSON.stringify(messageParamSets);

    useEffect(() => {
        if (!isOpen || !isAuthenticated) return undefined;
        if (messageParamSets.length === 0) {
            setMessages([]);
            return undefined;
        }

        const ac = new AbortController();
        abortRef.current?.abort();
        abortRef.current = ac;

        (async () => {
            setMessagesPending(true);
            setMessagesError(false);
            try {
                const results = await Promise.all(messageParamSets.map((params) =>
                    loadMessagesWithMarkRead({
                        params,
                        view,
                        markRead: markMessagesAsRead,
                        fetchList: fetchMessages,
                        signal: ac.signal,
                    })
                ));
                if (ac.signal.aborted) return;
                const unique = new Map();
                results.flatMap(({ list }) => list).forEach((message) => unique.set(message.id, message));
                setMessages([...unique.values()].sort((a, b) =>
                    new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
                ));
                if (results.some(({ marked }) => marked)) refreshUnread();
            } catch (e) {
                if (e?.name === "AbortError") return;
                setMessagesError(true);
                setMessages([]);
            } finally {
                if (!ac.signal.aborted) setMessagesPending(false);
            }
        })();

        return () => ac.abort();
        // messagesParamsKey serializes filter identity for exhaustive-deps
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, isAuthenticated, view, messagesParamsKey, refreshUnread]);

    const togglePanel = () => {
        setIsOpen((v) => !v);
    };

    const closePanel = () => {
        setIsOpen(false);
    };

    return {
        isOpen,
        view,
        VIEWS: NOTIFICATION_VIEWS,
        unreadCount,
        badgeText: formatUnreadBadge(unreadCount),
        panelTitle: "Уведомления",
        messages,
        messagesPending,
        messagesError,
        messagesParams,
        togglePanel,
        closePanel,
        refreshUnread,
        hasMessageFilterParams,
    };
}
