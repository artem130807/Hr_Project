import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { isWebPushSupported } from "../utils/webPushLogic";
import { registerPushServiceWorker, syncWebPushSubscription } from "../services/webPushClient";

export function useWebPush({ enabled = true } = {}) {
    const navigate = useNavigate();
    const [permission, setPermission] = useState(
        typeof Notification === "undefined" ? "unsupported" : Notification.permission
    );
    const supported = isWebPushSupported();

    const sync = useCallback(async (requestPermission) => {
        if (!enabled || !supported) return false;
        await registerPushServiceWorker();
        const ok = await syncWebPushSubscription({ requestPermission });
        setPermission(Notification.permission);
        return ok;
    }, [enabled, supported]);

    useEffect(() => {
        if (!enabled || !supported) return undefined;
        const onMessage = (event) => {
            if (event.data?.type === "hr-push-navigate" && event.data?.url) navigate(event.data.url);
        };
        navigator.serviceWorker.addEventListener("message", onMessage);
        sync(false);
        return () => navigator.serviceWorker.removeEventListener("message", onMessage);
    }, [enabled, navigate, supported, sync]);

    return { supported, permission, ensurePush: () => sync(true) };
}
