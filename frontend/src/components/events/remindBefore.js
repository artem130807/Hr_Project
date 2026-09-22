/** 0 is valid ("notify on the event day"); do not use `|| fallback`. */
export function normalizeRemindBefore(value, fallback = 3) {
    if (value === "" || value === null || value === undefined) {
        return fallback;
    }
    const n = Number(value);
    return Number.isFinite(n) && n >= 0 ? Math.floor(n) : fallback;
}
