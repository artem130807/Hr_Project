/** Build submit payload answers for professional public take. */

export function buildProfAnswerEntry({
    value = "",
    optionIndex = null,
    violations = [],
    forcedIncorrect = false,
} = {}) {
    const uniqueViolations = [...new Set((violations || []).filter(Boolean))];
    return {
        value: value != null ? String(value) : "",
        option_index: optionIndex == null ? null : Number(optionIndex),
        violations: uniqueViolations,
        forced_incorrect: Boolean(forcedIncorrect || uniqueViolations.length),
    };
}

export function markQuestionViolated(prevAnswers, questionId, violation) {
    const key = String(questionId);
    const prev = prevAnswers[key] || buildProfAnswerEntry();
    const violations = [...new Set([...(prev.violations || []), violation])];
    return {
        ...prevAnswers,
        [key]: {
            ...prev,
            violations,
            forced_incorrect: true,
        },
    };
}

export function answersForSubmit(answersById, questions) {
    const out = {};
    (questions || []).forEach((q) => {
        const key = String(q.id);
        const entry = answersById[key];
        if (!entry) return;
        const hasValue = String(entry.value || "").trim() || entry.option_index != null;
        const forced = Boolean(entry.forced_incorrect || (entry.violations || []).length);
        if (!hasValue && !forced) return;
        out[key] = buildProfAnswerEntry({
            value: entry.value,
            optionIndex: entry.option_index,
            violations: entry.violations,
            forcedIncorrect: forced,
        });
    });
    return out;
}

/** On timeout — ensure every unanswered question is marked forced incorrect. */
export function fillUnansweredAsTimedOut(answersById, questions) {
    const next = { ...answersById };
    (questions || []).forEach((q) => {
        const key = String(q.id);
        const prev = next[key];
        if (prev && (String(prev.value || "").trim() || prev.option_index != null || prev.forced_incorrect)) {
            return;
        }
        next[key] = buildProfAnswerEntry({
            value: prev?.value || "",
            optionIndex: prev?.option_index ?? null,
            violations: prev?.violations || [],
            forcedIncorrect: true,
        });
    });
    return next;
}
