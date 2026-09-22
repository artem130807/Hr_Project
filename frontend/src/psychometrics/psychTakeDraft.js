/** Durable in-progress psych take: survives tab/browser close via localStorage. */

export const PSYCH_TAKE_DRAFT_VERSION = 1;
export const PSYCH_TAKE_DRAFT_TTL_MS = 14 * 24 * 60 * 60 * 1000;
export const PSYCH_TAKE_DRAFT_PREFIX = "psych-take-draft:v1:";

export function psychTakeDraftScopeFromSearch(search = "") {
    const qs = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
    return qs.get("result_id") || qs.get("candidate_id") || "anon";
}

export function psychTakeDraftKey(instrumentId, scope = "anon") {
    const id = String(instrumentId || "unknown").trim() || "unknown";
    const slot = String(scope || "anon").trim() || "anon";
    return `${PSYCH_TAKE_DRAFT_PREFIX}${id}:${slot}`;
}

export function getBrowserLocalStorage() {
    if (typeof window === "undefined" || !window.localStorage) return null;
    return window.localStorage;
}

function safeParse(raw) {
    if (!raw) return null;
    try {
        const data = JSON.parse(raw);
        return data && typeof data === "object" ? data : null;
    } catch {
        return null;
    }
}

function clampIndex(index, length) {
    const n = Number(index);
    if (!Number.isInteger(n) || n < 0) return 0;
    if (!length) return 0;
    return Math.min(n, length - 1);
}

export function sanitizePsychTakeDraft(raw, { itemCodes = null, now = Date.now() } = {}) {
    if (!raw || typeof raw !== "object") return null;
    const savedAt = Number(raw.savedAt) || 0;
    if (savedAt && now - savedAt > PSYCH_TAKE_DRAFT_TTL_MS) return null;
    const codes = Array.isArray(raw.codes) ? raw.codes.map(String) : null;
    if (itemCodes) {
        const allowed = new Set(itemCodes);
        if (!codes || codes.length !== itemCodes.length || codes.some((code) => !allowed.has(code))) {
            return null;
        }
    }
    const answersIn = raw.answers && typeof raw.answers === "object" && !Array.isArray(raw.answers) ? raw.answers : {};
    const answers = {};
    Object.entries(answersIn).forEach(([code, value]) => {
        if (!itemCodes || itemCodes.includes(code)) answers[code] = value;
    });
    return {
        version: PSYCH_TAKE_DRAFT_VERSION,
        instrumentId: raw.instrumentId || null,
        seed: raw.seed ?? null,
        codes,
        answers,
        questionIndex: clampIndex(raw.questionIndex, codes?.length || 0),
        fullName: typeof raw.fullName === "string" ? raw.fullName : "",
        position: typeof raw.position === "string" ? raw.position : "",
        birthDate: typeof raw.birthDate === "string" ? raw.birthDate : "",
        startedAt: Number(raw.startedAt) || null,
        activeMs: Math.max(0, Number(raw.activeMs) || 0),
        latencies: raw.latencies && typeof raw.latencies === "object" && !Array.isArray(raw.latencies) ? raw.latencies : {},
        savedAt: savedAt || now,
    };
}

export function readPsychTakeDraft(instrumentId, { storage = getBrowserLocalStorage(), scope = "anon", itemCodes = null, now = Date.now() } = {}) {
    if (!storage) return null;
    const parsed = safeParse(storage.getItem(psychTakeDraftKey(instrumentId, scope)));
    return sanitizePsychTakeDraft(parsed, { itemCodes, now });
}

export function writePsychTakeDraft(instrumentId, snapshot, { storage = getBrowserLocalStorage(), scope = "anon", now = Date.now() } = {}) {
    if (!storage) return false;
    const payload = {
        version: PSYCH_TAKE_DRAFT_VERSION,
        instrumentId: instrumentId || null,
        seed: snapshot?.seed ?? null,
        codes: Array.isArray(snapshot?.codes) ? snapshot.codes : [],
        answers: snapshot?.answers && typeof snapshot.answers === "object" ? snapshot.answers : {},
        questionIndex: Number.isInteger(snapshot?.questionIndex) ? snapshot.questionIndex : 0,
        fullName: snapshot?.fullName || "",
        position: snapshot?.position || "",
        birthDate: snapshot?.birthDate || "",
        startedAt: snapshot?.startedAt ?? null,
        activeMs: snapshot?.activeMs ?? 0,
        latencies: snapshot?.latencies && typeof snapshot.latencies === "object" ? snapshot.latencies : {},
        savedAt: now,
    };
    try {
        storage.setItem(psychTakeDraftKey(instrumentId, scope), JSON.stringify(payload));
        return true;
    } catch {
        return false;
    }
}

export function clearPsychTakeDraft(instrumentId, { storage = getBrowserLocalStorage(), scope = "anon" } = {}) {
    if (!storage) return;
    try {
        storage.removeItem(psychTakeDraftKey(instrumentId, scope));
    } catch {
        /* ignore quota / private mode */
    }
}

export function memoryStorage(initial = {}) {
    const data = { ...initial };
    return {
        getItem(key) {
            return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null;
        },
        setItem(key, value) {
            data[key] = String(value);
        },
        removeItem(key) {
            delete data[key];
        },
        _data: data,
    };
}
