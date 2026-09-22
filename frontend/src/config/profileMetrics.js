/**
 * Copy for HR profile KPI cards (not logistics: trips / revenue).
 */
export const PROFILE_METRIC_LABELS = {
    interviews: "Мои собеседования",
    hired: "Трудоустроенные",
    inWork: "В работе",
    hours: "Часы работы",
};

export const PROFILE_METRIC_HINTS = {
    hiredStatus: "В работе",
};

export function interviewsWeekHint(count) {
    const n = Number(count);
    const value = Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
    return value > 0 ? `+${value} за эту неделю` : "0 за эту неделю";
}
