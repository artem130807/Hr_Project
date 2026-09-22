export const ADAPTATION_TAKE_STORAGE_KEY = "adaptationTake";

export const TAKE_ROLE_LABELS = {
    employee: "Сотрудник",
    manager: "Руководитель",
    hr: "HR",
};

export function adaptationFormPath(token) {
    if (!token) return "";
    return `/adaptation/forms/${encodeURIComponent(token)}`;
}

export function adaptationFormAbsoluteUrl(token, origin = (typeof window !== "undefined" ? window.location.origin : "")) {
    const path = adaptationFormPath(token);
    return path ? `${origin}${path}` : "";
}

export function rememberAdaptationTake(payload = {}, storage) {
    const record = {
        employeeId: payload.employee_id ?? payload.employeeId ?? null,
        temporaryEmployeeId: payload.temporary_employee_id ?? payload.temporaryEmployeeId ?? null,
        enrollmentId: payload.enrollment_id ?? payload.enrollmentId ?? null,
        checkpointId: payload.checkpoint_id ?? payload.checkpointId ?? null,
        role: payload.role ?? null,
        token: payload.token ?? null,
        savedAt: new Date().toISOString(),
    };
    try {
        const target = storage === undefined ? window.localStorage : storage;
        if (!target) return null;
        target.setItem(ADAPTATION_TAKE_STORAGE_KEY, JSON.stringify(record));
    } catch {
        // Remembering a shortcut is optional; never fail form loading/submission.
        return null;
    }
    return record;
}

export function readAdaptationTake(storage) {
    try {
        const target = storage === undefined ? window.localStorage : storage;
        if (!target) return null;
        const raw = target.getItem(ADAPTATION_TAKE_STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

export async function copyText(value) {
    const text = String(value || "");
    if (!text) return false;
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
    }
    if (typeof document === "undefined") return false;
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok;
}

export function employeeTakeLinks(links = []) {
    return (Array.isArray(links) ? links : []).filter((item) => item?.role === "employee" && item?.token);
}
