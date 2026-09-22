import { http } from "../utils/http";
import { getAccessToken } from "../utils/tokenStorage";

const toBool = (val, fallback = false) => {
    if (val === true || val === false) return val;
    if (val === 1 || val === "1") return true;
    if (val === 0 || val === "0") return false;
    if (typeof val === "string") {
        const s = val.trim().toLowerCase();
        if (s === "true") return true;
        if (s === "false") return false;
    }
    return fallback;
};

const pickEnabled = (payload) => {
    if (typeof payload === "boolean") return payload;

    const obj = Array.isArray(payload) ? payload[0] : payload;
    if (!obj || typeof obj !== "object") return null;

    const candidates = [
        obj.auto_processing, obj.autoProcessing, obj.auto_process,
        obj.enabled, obj.is_active, obj.isActive, obj.subscribed,
        obj.has_subscription, obj.hasSubscription,
        obj?.data?.auto_processing, obj?.data?.enabled, obj?.data?.is_active, obj?.data?.subscribed,
        obj?.data?.has_subscription, obj?.data?.hasSubscription,
        obj?.subscription?.enabled, obj?.subscription?.is_active
    ];

    for (const v of candidates) {
        if (v !== undefined && v !== null) return toBool(v, null);
    }
    return null;
};

export const getAutoSubscription = async () => {
    const data = await http.get("/hh/subscription");
    const enabled = pickEnabled(data);
    return enabled ?? false;
};

export const setAutoSubscription = async (enabled) => {
    const query = `subscribe=${enabled ? "true" : "false"}`;
    return http.post(`/hh/negotiations/subscribe?${query}`, {});
};

export const isAuthorizedOnHH = () => {
    try {
        return Boolean(getAccessToken());
    } catch {
        return false;
    }
};
