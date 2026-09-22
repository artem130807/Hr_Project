/** Adaptation checkpoint rules (mirrors backend app.adaptation.rules). */

export const KIND_WEEK_1 = "week_1";
export const KIND_MONTH_1 = "month_1";
export const KIND_MONTH_2 = "month_2";
export const KIND_CONTROL_2M = "control_2m";
export const KIND_EXTRA = "extra";

export const ROLE_EMPLOYEE = "employee";
export const ROLE_MANAGER = "manager";
export const ROLE_HR = "hr";

export const STATUS_PLANNED = "planned";
export const STATUS_COLLECTING = "collecting";
export const STATUS_OVERDUE = "overdue";
export const STATUS_DATA_COLLECTED = "data_collected";
export const STATUS_DRAFT_READY = "draft_ready";
export const STATUS_COMPLETED = "completed";
export const STATUS_FORCED_COMPLETED = "forced_completed";

export const RISK_NONE = "uncalculated";
export const RISK_LOW = "low";
export const RISK_MEDIUM = "medium";
export const RISK_HIGH = "high";
export const RISK_CRITICAL = "critical";

export const KIND_LABELS = {
    [KIND_WEEK_1]: "1 неделя",
    [KIND_MONTH_1]: "1 месяц",
    [KIND_MONTH_2]: "2 месяца",
    [KIND_CONTROL_2M]: "Контроль 2 месяца",
    [KIND_EXTRA]: "Доп. точка",
};

export const STATUS_LABELS = {
    [STATUS_PLANNED]: "Запланирован",
    [STATUS_COLLECTING]: "Сбор ответов",
    [STATUS_OVERDUE]: "Просрочен",
    [STATUS_DATA_COLLECTED]: "Данные собраны",
    [STATUS_DRAFT_READY]: "Черновик сформирован",
    [STATUS_COMPLETED]: "Завершен",
    [STATUS_FORCED_COMPLETED]: "Завершен принудительно",
};

export const RISK_LABELS = {
    [RISK_NONE]: "Не рассчитан",
    [RISK_LOW]: "Низкий",
    [RISK_MEDIUM]: "Средний",
    [RISK_HIGH]: "Высокий",
    [RISK_CRITICAL]: "Критический",
};

export const OUTCOME_LABELS = {
    [RISK_HIGH]: "Критическая ситуация",
    [RISK_CRITICAL]: "Критическая ситуация",
    [RISK_MEDIUM]: "Требует внимания",
    [RISK_LOW]: "Стабильно",
    [RISK_NONE]: "Не рассчитан",
};

const KINDS_WITHOUT_MANAGER = new Set([KIND_WEEK_1, KIND_CONTROL_2M, KIND_EXTRA]);
const KINDS_HR_ONLY = new Set([KIND_CONTROL_2M]);
const CORE_EMPLOYEE_IDS = ["core_e1", "core_e2", "core_e3", "core_e4", "core_e5"];
const STAY_SIGNAL_IDS = ["m1_stay", "m2_stay"];

export function rolesForKind(kind) {
    if (KINDS_HR_ONLY.has(kind)) return [ROLE_HR];
    if (KINDS_WITHOUT_MANAGER.has(kind)) return [ROLE_EMPLOYEE, ROLE_HR];
    return [ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_HR];
}

export function nextBusinessDay(value) {
    const d = value instanceof Date ? new Date(value.getFullYear(), value.getMonth(), value.getDate()) : new Date(value);
    while (d.getDay() === 0 || d.getDay() === 6) {
        d.setDate(d.getDate() + 1);
    }
    return d;
}

export function addMonths(d, months) {
    const year = d.getFullYear();
    const monthIndex = d.getMonth() + months;
    const lastDay = new Date(year, monthIndex + 1, 0).getDate();
    const day = Math.min(d.getDate(), lastDay);
    return new Date(year, monthIndex, day);
}

export function planDateFor(kind, hired, extraOn) {
    const h = hired instanceof Date ? hired : new Date(hired);
    let planned;
    if (kind === KIND_WEEK_1) {
        planned = new Date(h);
        planned.setDate(planned.getDate() + 7);
    } else if (kind === KIND_MONTH_1) planned = addMonths(h, 1);
    else if (kind === KIND_MONTH_2 || kind === KIND_CONTROL_2M) planned = addMonths(h, 2);
    else if (kind === KIND_EXTRA) planned = extraOn instanceof Date ? extraOn : new Date(extraOn);
    else throw new Error(`Неизвестный этап: ${kind}`);
    return nextBusinessDay(planned);
}

/** Overdue starts 09:00 Samara (UTC+4) the calendar day after plan date. */
export function overdueStartsAt(plan) {
    const p = plan instanceof Date ? plan : new Date(plan);
    const next = new Date(p.getFullYear(), p.getMonth(), p.getDate() + 1, 9, 0, 0);
    return next;
}

export function submittedRoles(answers) {
    return new Set((answers || []).map((a) => a.role).filter(Boolean));
}

export function computeStatus({ kind, planDate, answers, now = new Date(), closed = false, forcedCompleted = false, draftReady = false }) {
    if (forcedCompleted) return STATUS_FORCED_COMPLETED;
    if (closed) return STATUS_COMPLETED;
    if (draftReady) return STATUS_DRAFT_READY;
    const roles = rolesForKind(kind);
    const done = submittedRoles(answers);
    const preHr = roles.filter((r) => r !== ROLE_HR);
    const employeeRequired = roles.includes(ROLE_EMPLOYEE);
    const employeeDone = done.has(ROLE_EMPLOYEE);
    const preHrDone = preHr.every((r) => done.has(r));
    const hrDone = done.has(ROLE_HR);
    if (preHrDone && hrDone) return STATUS_COMPLETED;
    const plan = planDate instanceof Date ? planDate : new Date(planDate);
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const planDay = new Date(plan.getFullYear(), plan.getMonth(), plan.getDate());
    if (preHrDone && !hrDone && (preHr.length > 0 || today.getTime() >= planDay.getTime())) {
        return STATUS_DATA_COLLECTED;
    }
    if (employeeRequired && !employeeDone && now.getTime() >= overdueStartsAt(plan).getTime()) return STATUS_OVERDUE;
    if (today.getTime() >= planDay.getTime()) return STATUS_COLLECTING;
    return STATUS_PLANNED;
}

const NEGATIVE_ITEM_IDS = new Set();

function scaleValues(payload) {
    const values = [];
    Object.entries(payload || {}).forEach(([key, raw]) => {
        if (key.startsWith("_")) return;
        let n;
        if (typeof raw === "boolean") n = raw ? 5 : 1;
        else {
            n = Number(raw);
            if (!Number.isInteger(n)) return;
        }
        if (n < 1 || n > 5) return;
        if (NEGATIVE_ITEM_IDS.has(key)) n = 6 - n;
        values.push(n);
    });
    return values;
}

function intScore(raw) {
    const n = Number(raw);
    if (!Number.isInteger(n) || n < 1 || n > 5) return null;
    return n;
}

export function computeRisk(employeePayload, kind) {
    if (kind === KIND_CONTROL_2M) return RISK_NONE;
    const payload = employeePayload || {};
    let cores = CORE_EMPLOYEE_IDS.map((id) => intScore(payload[id])).filter((v) => v != null);
    if (!cores.length) {
        const values = scaleValues(payload);
        if (!values.length) return RISK_NONE;
        const avg = values.reduce((s, v) => s + v, 0) / values.length;
        if (avg >= 4) return RISK_LOW;
        if (avg >= 3) return RISK_MEDIUM;
        return RISK_HIGH;
    }
    let strong = cores.filter((v) => v <= 2).length;
    const medium = cores.filter((v) => v === 3).length;
    let intentionLow = false;
    for (const sid of STAY_SIGNAL_IDS) {
        const stay = intScore(payload[sid]);
        if (stay != null && stay <= 2) {
            strong += 1;
            intentionLow = true;
            break;
        }
    }
    const otherStrong = strong - (intentionLow ? 1 : 0);
    if (strong >= 3 && (!intentionLow || otherStrong >= 2)) return RISK_CRITICAL;
    if (strong >= 2) return RISK_HIGH;
    if (strong === 1 || medium >= 2) return RISK_MEDIUM;
    return RISK_LOW;
}

export function outcomeLabel(risk, { kind, employeeSubmitted } = {}) {
    if (kind === KIND_CONTROL_2M && employeeSubmitted) {
        return risk === RISK_NONE ? "Без анкеты" : OUTCOME_LABELS[risk];
    }
    return OUTCOME_LABELS[risk] || OUTCOME_LABELS[RISK_NONE];
}

function parseCalendarDate(value) {
    if (value instanceof Date) return new Date(value.getFullYear(), value.getMonth(), value.getDate());
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)) {
        const [y, m, d] = value.slice(0, 10).split("-").map(Number);
        return new Date(y, m - 1, d);
    }
    const d = new Date(value);
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function attentionBucket(status, planDate, weekStartDate, weekEndDate) {
    if (status === STATUS_OVERDUE) return "overdue";
    if (status === STATUS_DATA_COLLECTED) return "ready_hr";
    const plan = parseCalendarDate(planDate);
    const start = parseCalendarDate(weekStartDate);
    const end = parseCalendarDate(weekEndDate);
    if (status === STATUS_PLANNED && plan >= start && plan <= end) return "this_week";
    return null;
}

export function weekStart(today) {
    const t = today instanceof Date ? today : new Date(today);
    const day = new Date(t.getFullYear(), t.getMonth(), t.getDate());
    const iso = (day.getDay() + 6) % 7;
    day.setDate(day.getDate() - iso);
    return day;
}

export function weekEnd(today) {
    const t = today instanceof Date ? today : new Date(today);
    const day = new Date(t.getFullYear(), t.getMonth(), t.getDate());
    const iso = (day.getDay() + 6) % 7;
    day.setDate(day.getDate() + (6 - iso));
    return day;
}

export function formatDateRu(value) {
    if (!value) return "—";
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)) {
        const [y, m, d] = value.slice(0, 10).split("-").map(Number);
        const dd = String(d).padStart(2, "0");
        const mm = String(m).padStart(2, "0");
        return `${dd}.${mm}.${y}`;
    }
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    return `${dd}.${mm}.${d.getFullYear()}`;
}

export function initials(name) {
    return String(name || "")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((p) => p[0])
        .join("")
        .toUpperCase();
}
