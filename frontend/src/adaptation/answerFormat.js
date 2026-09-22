export function formatQuestionAnswer(question, value) {
    if (Array.isArray(value)) return value.join(", ");
    const specialOptions = question?.special_options || [];
    const special = specialOptions.find(
        (option, index) => option.value === value || (value === "na" && index === 0)
    );
    if (special) return special.label;
    if (["scale_1_5", "scale_na", "scale_obs"].includes(question?.type) && Number.isFinite(Number(value))) {
        return `${value} из 5`;
    }
    return String(value ?? "");
}
