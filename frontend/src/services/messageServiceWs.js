import {
    buildNotificationsWsURL,
    parseNotificationPayload,
} from "../utils/notificationWsLogic";

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 15000;
const MAX_CONSECUTIVE_FAILURES = 6;

/**
 * WebSocket manager for message-service `/api/ws`.
 */
export function createMessageServiceSocket({
    getToken,
    onNotification,
    onStatus,
    getBaseURL,
    getBaseCandidates,
} = {}) {
    let socket = null;
    let closedByUser = false;
    let reconnectAttempt = 0;
    let reconnectTimer = null;
    let generation = 0;
    let consecutiveFailures = 0;

    function status(next) {
        if (typeof onStatus === "function") onStatus(next);
    }

    function clearReconnect() {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    }

    function scheduleReconnect(gen) {
        if (closedByUser || gen !== generation) return;
        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            status("disabled");
            return;
        }
        clearReconnect();
        const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * (2 ** reconnectAttempt));
        reconnectAttempt += 1;
        reconnectTimer = setTimeout(() => {
            if (closedByUser || gen !== generation) return;
            connect();
        }, delay);
    }

    function connect() {
        clearReconnect();
        const token = typeof getToken === "function" ? getToken() : "";
        const candidateBases = typeof getBaseCandidates === "function"
            ? getBaseCandidates()
            : [typeof getBaseURL === "function" ? getBaseURL() : "/message-service"];
        const urls = (Array.isArray(candidateBases) ? candidateBases : [candidateBases])
            .map((base) => buildNotificationsWsURL(base, token))
            .filter(Boolean);
        if (urls.length === 0) {
            status("idle");
            return;
        }

        const gen = ++generation;
        closedByUser = false;

        if (socket) {
            const prev = socket;
            socket = null;
            try {
                prev.onclose = null;
                prev.onerror = null;
                prev.onmessage = null;
                prev.close();
            } catch {
                // ignore
            }
        }

        const connectAt = Date.now();
        const tryConnect = (index) => {
            if (index >= urls.length || gen !== generation || closedByUser) {
                status("closed");
                scheduleReconnect(gen);
                return;
            }

            status("connecting");
            const ws = new WebSocket(urls[index]);
            socket = ws;
            let opened = false;

            ws.onopen = () => {
                if (gen !== generation) return;
                opened = true;
                reconnectAttempt = 0;
                consecutiveFailures = 0;
                status("open");
            };

            ws.onmessage = (event) => {
                if (gen !== generation) return;
                const payload = parseNotificationPayload(event.data);
                if (payload && typeof onNotification === "function") {
                    onNotification(payload);
                }
            };

            ws.onerror = () => {
                if (gen !== generation) return;
                status("error");
            };

            ws.onclose = () => {
                if (gen !== generation) return;
                if (socket === ws) socket = null;
                if (opened) {
                    status("closed");
                    scheduleReconnect(gen);
                    return;
                }

                // Handshake failed; try fallback endpoint, then backoff reconnect.
                const elapsed = Date.now() - connectAt;
                if (index + 1 < urls.length) {
                    tryConnect(index + 1);
                    return;
                }
                if (elapsed < 2000) {
                    consecutiveFailures += 1;
                }
                status("closed");
                scheduleReconnect(gen);
            };
        };

        tryConnect(0);
    }

    function disconnect() {
        closedByUser = true;
        generation += 1;
        clearReconnect();
        if (socket) {
            const prev = socket;
            socket = null;
            try {
                prev.onclose = null;
                prev.onerror = null;
                prev.onmessage = null;
                prev.close();
            } catch {
                // ignore
            }
        }
        reconnectAttempt = 0;
        consecutiveFailures = 0;
        status("idle");
    }

    return { connect, disconnect };
}
