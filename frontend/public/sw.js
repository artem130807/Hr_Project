/* global self, clients */
self.addEventListener("install", (event) => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("push", (event) => event.waitUntil(handlePush(event)));
self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    event.waitUntil(handleNotificationClick(event.notification));
});

async function handlePush(event) {
    let payload = null;
    try { payload = event.data ? event.data.json() : null; } catch {
        try { payload = event.data ? JSON.parse(event.data.text()) : null; } catch { payload = null; }
    }
    if (!payload || payload.content == null) return;
    const windows = await clients.matchAll({ type: "window", includeUncontrolled: true });
    const hasFocused = windows.some((client) => client.focused);
    const body = String(payload.content || "").trim() || "Новое уведомление";
    const text = body.length > 180 ? `${body.slice(0, 177)}…` : body;
    const tag = payload.id != null ? `hr-msg-${payload.id}` : "hr-msg";
    await self.registration.showNotification("HR Platform", {
        body: text,
        tag,
        renotify: true,
        silent: hasFocused,
        data: { url: payload.url || fallbackUrl(payload) },
    });
    if (hasFocused) {
        const shown = await self.registration.getNotifications({ tag });
        shown.forEach((notification) => notification.close());
    }
}

function fallbackUrl(payload) {
    const type = String(payload.entity_type || "").toLowerCase();
    const routes = {
        hiring_request: "/requests",
        vacancy: "/vacancies",
        candidate: "/candidates",
        employee: "/employees",
        event: "/events",
        test: "/tests",
    };
    return routes[type] || "/notifications";
}

async function handleNotificationClick(notification) {
    const path = notification?.data?.url || "/notifications";
    const destination = /^https?:\/\//i.test(path)
        ? path
        : new URL(String(path).replace(/^\/+/, ""), self.registration.scope).href;
    const windows = await clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of windows) {
        try { if (new URL(client.url).origin !== self.location.origin) continue; } catch { continue; }
        if (client.focus) await client.focus();
        if (typeof client.navigate === "function") {
            try { await client.navigate(destination); return; } catch { /* postMessage fallback */ }
        }
        client.postMessage({ type: "hr-push-navigate", url: path });
        return;
    }
    await clients.openWindow(destination);
}
