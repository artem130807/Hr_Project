function trimSlash(value) {
    return String(value || "").replace(/\/$/, "");
}

/** Front hosts that already reverse-proxy `/v1` to database-service. */
const SAME_ORIGIN_API_HOSTS = new Set([
    "hr-web.alt-cargo.tw1.ru",
    "localhost",
    "127.0.0.1",
]);

/**
 * Prefer same-origin `/v1`. Prod web already proxies it; calling
 * hr-platform from the browser fails for many clients (split VPN, http origin, CORS).
 * Opt out: REACT_APP_FORCE_REMOTE_API=true
 */
export function resolvePublicApiUrl({
    nodeEnv = process.env.NODE_ENV,
    forceRemote = process.env.REACT_APP_FORCE_REMOTE_API,
    configured = process.env.REACT_APP_API_URL,
    hostname = typeof window !== "undefined" ? window.location.hostname : "",
} = {}) {
    if (String(forceRemote) === "true") {
        return trimSlash(configured);
    }
    if (nodeEnv === "development") {
        return "";
    }
    if (SAME_ORIGIN_API_HOSTS.has(hostname)) {
        return "";
    }
    return trimSlash(configured);
}

export const API_URL = resolvePublicApiUrl();
export const API_PREFIX = "/v1";
/**
 * HH traffic goes through database-service `/v1/hh/...` (same host as API_URL).
 * Do not append `/hh` — prod ingress returns 404 for `/hh/*`.
 */
export const HH_API_URL = API_URL
    ? trimSlash(process.env.REACT_APP_HH_API_URL || API_URL)
    : "";
/** AI calls go through database-service proxies by default. */
export const AI_API_URL = API_URL
    ? trimSlash(process.env.REACT_APP_AI_API_URL || API_URL)
    : "";


export const DEPARTMENTS = [
    "hr",
    "логистический",
    "делопроизводственный",
    "юридический",
    "бухгалтерия",
    "art",
    "IT",
    "развитие",
]

export const WORK_FORMATS = ["удалённый", "гибридный", "офис", "сменный"];

export const EMPLOYMENT_TYPES = [
    "полная",
    "частичная",
    "временная"
]

export const GENDERS = [
    "мужчина",
    "женщина"
]

export const WORK_EXPERIENCE = [
    "0-1 год",
    "1-3 года",
    "3-6 лет",
    "6+ лет"
]

export const UPDATE_DATES = [
    "7-14 дней",
    "30 дней",
    "1 год"
]

export const MARITAL_STATUS = [
    "в браке",
    "не в браке",
    "в разводе",
    "вдовец/вдова",
]

export const TEST_TYPES = [
    "url",
    "Вопросно-ответная форма"
]

export const RESULT_TYPES = [
    "текстовый результат",
    "текстовый результат + скриншот",
    "результат обрабатывается сторонним сервисом"
]
