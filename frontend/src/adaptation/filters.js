import { attentionBucket, weekEnd, weekStart } from "./rules";

function startOfDay(value) {
    const date = new Date(value);
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function checkpointDateBucket(planDate, today = new Date()) {
    if (!planDate) return "later";
    const base = startOfDay(today);
    const date = startOfDay(`${planDate}T12:00:00`);
    const days = Math.round((date - base) / 86400000);
    if (days < 0) return "overdue";
    if (days === 0) return "today";
    if (days <= 14) return "two_weeks";
    return "later";
}

export function filterCheckpoints(items, { q, department, kind, risk, route, outcome, status, hideCompleted, dateScope } = {}, today = new Date()) {
    const needle = String(q || "").trim().toLowerCase();
    return (items || []).filter((row) => {
        if (needle) {
            const hay = `${row.full_name || ""} ${row.position || ""}`.toLowerCase();
            if (!hay.includes(needle)) return false;
        }
        if (department && row.department !== department) return false;
        if (kind && row.kind !== kind) return false;
        if (risk && row.risk !== risk) return false;
        if (route && row.route !== route) return false;
        if (outcome && row.outcome !== outcome) return false;
        if (status && row.status !== status) return false;
        if (hideCompleted && row.status === "completed") return false;
        if (dateScope && checkpointDateBucket(row.plan_date, today) !== dateScope) return false;
        return true;
    });
}

export function attentionFrom(items, today = new Date()) {
    const start = weekStart(today);
    const end = weekEnd(today);
    let overdue = 0;
    let thisWeek = 0;
    let readyHr = 0;
    (items || []).forEach((row) => {
        const bucket = attentionBucket(row.status, row.plan_date, start, end);
        if (bucket === "overdue") overdue += 1;
        else if (bucket === "this_week") thisWeek += 1;
        else if (bucket === "ready_hr") readyHr += 1;
    });
    return { overdue, this_week: thisWeek, ready_hr: readyHr };
}
