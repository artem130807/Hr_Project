export const EVENT_TYPE_OPTIONS = [
    { value: "birthday", label: "День рождения" },
    { value: "child_birthday", label: "ДР ребёнка" },
    { value: "work_anniversary", label: "Годовщина работы" },
    { value: "interview", label: "Собеседование" },
    { value: "permanent", label: "Постоянное" },
    { value: "other", label: "Другое" },
];

export const REPEAT_INTERVAL_OPTIONS = [
    { value: "day", label: "день" },
    { value: "week", label: "неделю" },
    { value: "month", label: "месяц" },
    { value: "year", label: "год" },
];

/** Имя сотрудника нужно для ДР и ДР ребёнка. Собеседование и постоянное поле не используют. */
export const eventTypeRequiresEmployeeName = (type) =>
    type === "birthday" || type === "child_birthday";

export const isPermanentEventType = (type) => type === "permanent";

export function formatRepeatInterval(count, unit) {
    const n = Number(count) || 1;
    if (!unit) return "";
    if (n === 1) {
        const once = {
            day: "каждый день",
            week: "каждую неделю",
            month: "каждый месяц",
            year: "каждый год",
        };
        return once[unit] || unit;
    }
    const many = {
        day: "дн.",
        week: "нед.",
        month: "мес.",
        year: "г.",
    };
    return `каждые ${n} ${many[unit] || unit}`;
}

const TYPE_META = {
    birthday: {
        label: "День рождения",
        shortLabel: "ДР",
        icon: "🎁",
        stripeClass: "bg-blue-400",
    },
    child_birthday: {
        label: "ДР ребёнка",
        shortLabel: "ДР ребёнка",
        icon: "🧸",
        stripeClass: "bg-pink-400",
    },
    work_anniversary: {
        label: "Годовщина",
        shortLabel: "Годовщина",
        icon: "💼",
        stripeClass: "bg-amber-400",
    },
    interview: {
        label: "Собеседование",
        shortLabel: "Собеседование",
        icon: "🗓️",
        stripeClass: "bg-emerald-400",
    },
    permanent: {
        label: "Постоянное",
        shortLabel: "Постоянное",
        icon: "🔁",
        stripeClass: "bg-violet-400",
    },
    other: {
        label: "Другое",
        shortLabel: "Другое",
        icon: "📝",
        stripeClass: "bg-slate-400",
    },
};

export const getEventTypeMeta = (type) =>
    TYPE_META[type] || {
        label: type || "Событие",
        shortLabel: type || "Событие",
        icon: "📅",
        stripeClass: "bg-slate-300",
    };
