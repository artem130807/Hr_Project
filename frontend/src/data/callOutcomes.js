export const CALL_OUTCOMES = {
    pending: { label: "Определяется", className: "bg-slate-50 text-slate-600 border-slate-200" },
    interested: { label: "Интерес", className: "bg-emerald-50 text-emerald-800 border-emerald-100" },
    interview: { label: "Собеседование", className: "bg-amber-50 text-amber-800 border-amber-100" },
    callback: { label: "Перезвон", className: "bg-sky-50 text-sky-800 border-sky-100" },
    rejected: { label: "Отказ", className: "bg-rose-50 text-rose-800 border-rose-100" },
    dropped: { label: "Сброс", className: "bg-slate-100 text-slate-600 border-slate-200" },
};

export const CALL_DIRECTIONS = {
    incoming: { label: "Входящий", short: "Вх" },
    outgoing: { label: "Исходящий", short: "Исх" },
};

export function normalizeCallOutcome(status) {
    const key = String(status || "pending").trim();
    if (key === "no_answer") return "dropped";
    if (key === "interest") return "interested";
    if (CALL_OUTCOMES[key]) return key;
    return "pending";
}
