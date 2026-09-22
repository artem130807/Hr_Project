function asList(value) {
    if (Array.isArray(value)) return value;
    if (value == null || value === "") return [];
    return [value];
}

function matchRule(rule, values, coreHistory) {
    const field = rule.field;
    const raw = values?.[field];
    if (rule.lte != null) {
        const n = Number(raw);
        return Number.isFinite(n) && n <= rule.lte;
    }
    if (Object.prototype.hasOwnProperty.call(rule, "eq")) {
        return String(raw) === String(rule.eq);
    }
    if (rule.in) return rule.in.includes(raw);
    if (rule.not_in) return !rule.not_in.includes(raw);
    if (rule.not_only) {
        const list = asList(raw);
        if (!list.length) return false;
        return !(list.length === 1 && rule.not_only.includes(list[0]));
    }
    if (rule.delta_gte != null) {
        const curr = Number(raw);
        const prev = Number(coreHistory?.[field]);
        if (!Number.isFinite(curr) || !Number.isFinite(prev)) return false;
        return Math.abs(curr - prev) >= rule.delta_gte;
    }
    return true;
}

export function isQuestionVisible(question, values, coreHistory = {}) {
    const rule = question?.show_if;
    if (!rule) return true;
    if (Array.isArray(rule.any)) {
        return rule.any.some((item) => matchRule(item, values, coreHistory));
    }
    return matchRule(rule, values, coreHistory);
}
