import {
    CALL_LIST_ALLOWED_PHONES,
    callInvolvesAllowedPhones,
    isPhoneQuery,
    phoneMatches,
} from "./phoneSearch";

export function formatCallDuration(sec) {
    const total = Math.max(0, Math.floor(Number(sec) || 0));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
}

export function filterCalls(
    calls,
    { phoneQuery, direction, outcome, allowedPhones = CALL_LIST_ALLOWED_PHONES } = {}
) {
    const list = Array.isArray(calls) ? calls : [];
    const phone = String(phoneQuery || "").trim();
    return list.filter((call) => {
        if (!callInvolvesAllowedPhones(call, allowedPhones)) return false;
        if (direction && direction !== "all" && call.direction !== direction) return false;
        if (outcome && outcome !== "all" && call.outcome !== outcome) return false;
        if (phone && isPhoneQuery(phone)) {
            const hit =
                phoneMatches(call.phone, phone) ||
                phoneMatches(call.operatorPhone, phone);
            if (!hit) return false;
        }
        return true;
    });
}
