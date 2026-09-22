import { useEffect, useRef } from "react";
import { subscribeNotifications } from "../../services/notificationsApi";
import { useAlertContext } from "../../context/AlertContext";
import {
    notificationIsVisibleForUser,
    notificationToastMessage,
    parseNotificationPayload,
} from "../../utils/notificationWsLogic";

/**
 * Invisible host: listens for realtime notifications → toast + unread refresh.
 * Mirrors ERP NotificationToaster (mock bus today, WS later).
 */
export default function NotificationRealtime({ enabled = true, userId, roleId, onIncoming }) {
    const { showAlert } = useAlertContext();
    const onIncomingRef = useRef(onIncoming);
    onIncomingRef.current = onIncoming;

    useEffect(() => {
        if (!enabled) return undefined;

        const unsub = subscribeNotifications((raw) => {
            const payload = parseNotificationPayload(
                typeof raw === "string"
                    ? raw
                    : { type: "notification", ...raw, content: raw?.content ?? "" }
            );
            if (!payload) return;
            if (!notificationIsVisibleForUser(payload, userId, roleId)) return;

            const text = notificationToastMessage(payload);
            if (text) showAlert(text, "info");
            onIncomingRef.current?.(payload);
        });

        return () => unsub();
    }, [enabled, showAlert, userId, roleId]);

    return null;
}
