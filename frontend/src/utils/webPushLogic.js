export function urlBase64ToUint8Array(base64String) {
    const raw = String(base64String || "").trim();
    if (!raw) return new Uint8Array();
    const padding = "=".repeat((4 - (raw.length % 4)) % 4);
    const base64 = (raw + padding).replace(/-/g, "+").replace(/_/g, "/");
    const binary = typeof atob === "function"
        ? atob(base64)
        : Buffer.from(base64, "base64").toString("binary");
    return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

export function isWebPushSupported(g = typeof window !== "undefined" ? window : {}) {
    return typeof g.Notification === "function"
        && !!g.navigator?.serviceWorker
        && typeof g.PushManager === "function";
}

export function subscriptionToPayload(subscription) {
    if (!subscription || typeof subscription.toJSON !== "function") return null;
    const json = subscription.toJSON();
    if (!json?.endpoint || !json.keys?.p256dh || !json.keys?.auth) return null;
    return { endpoint: json.endpoint, keys: { p256dh: json.keys.p256dh, auth: json.keys.auth } };
}

export function parseVapidKeyPayload(data) {
    const enabled = data?.enabled === true
        && typeof data.public_key === "string"
        && data.public_key.length > 0;
    return { enabled, publicKey: enabled ? data.public_key : "" };
}

export const WEB_PUSH_VAPID_STORAGE_KEY = "hr-web-push-vapid";

export function readStoredVapidKey(storage = typeof window !== "undefined" ? window.localStorage : null) {
    try { return storage?.getItem?.(WEB_PUSH_VAPID_STORAGE_KEY) || ""; } catch { return ""; }
}

export function writeStoredVapidKey(
    publicKey,
    storage = typeof window !== "undefined" ? window.localStorage : null
) {
    try {
        if (publicKey) storage?.setItem?.(WEB_PUSH_VAPID_STORAGE_KEY, publicKey);
        else storage?.removeItem?.(WEB_PUSH_VAPID_STORAGE_KEY);
    } catch { /* private mode/quota */ }
}

export function shouldReplacePushSubscription(storedKey, nextKey) {
    return !!nextKey && !!storedKey && storedKey !== nextKey;
}
