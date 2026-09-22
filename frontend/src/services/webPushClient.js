import { getAccessToken } from "../utils/tokenStorage";
import {
    deletePushSubscription,
    fetchVapidPublicKey,
    savePushSubscription,
} from "./notificationsApi";
import {
    isWebPushSupported,
    parseVapidKeyPayload,
    readStoredVapidKey,
    shouldReplacePushSubscription,
    subscriptionToPayload,
    urlBase64ToUint8Array,
    writeStoredVapidKey,
} from "../utils/webPushLogic";

let registrationPromise = null;

export async function registerPushServiceWorker() {
    if (!isWebPushSupported()) return null;
    if (!registrationPromise) {
        registrationPromise = navigator.serviceWorker.register("/sw.js", { scope: "/" })
            .then(() => navigator.serviceWorker.ready)
            .catch((err) => {
                registrationPromise = null;
                console.warn("web push: service worker register failed", err);
                return null;
            });
    }
    return registrationPromise;
}

async function currentPushSubscription() {
    const registration = await registerPushServiceWorker();
    return registration?.pushManager?.getSubscription() || null;
}

export async function syncWebPushSubscription({ requestPermission = false } = {}) {
    if (!isWebPushSupported() || !getAccessToken()) return false;
    try {
        const vapid = parseVapidKeyPayload(await fetchVapidPublicKey());
        if (!vapid.enabled) return false;
        let permission = Notification.permission;
        if (permission === "default" && requestPermission) permission = await Notification.requestPermission();
        if (permission !== "granted") return false;

        const registration = await registerPushServiceWorker();
        if (!registration?.pushManager) return false;
        let subscription = await registration.pushManager.getSubscription();
        if (subscription && shouldReplacePushSubscription(readStoredVapidKey(), vapid.publicKey)) {
            await subscription.unsubscribe();
            subscription = null;
        }
        if (!subscription) {
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(vapid.publicKey),
            });
        }
        const payload = subscriptionToPayload(subscription);
        if (!payload) return false;
        await savePushSubscription(payload);
        writeStoredVapidKey(vapid.publicKey);
        return true;
    } catch (err) {
        console.warn("web push: sync failed", err);
        return false;
    }
}

export async function unsyncWebPushSubscription() {
    if (!isWebPushSupported()) return;
    try {
        const subscription = await currentPushSubscription();
        if (!subscription) return;
        const payload = subscriptionToPayload(subscription);
        if (payload && getAccessToken()) {
            try { await deletePushSubscription(payload); } catch { /* logout continues */ }
        }
        await subscription.unsubscribe();
        writeStoredVapidKey("");
    } catch (err) {
        console.warn("web push: unsync failed", err);
    }
}
