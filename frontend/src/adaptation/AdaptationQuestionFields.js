import { isQuestionVisible } from "./showIf";

function ScaleSelect({ value, onChange, disabled, specialOptions = [] }) {
    const selectValue = value === "na" && specialOptions.length
        ? specialOptions[0].value
        : (value ?? "");
    return (
        <select
            className="mt-1 w-full border rounded-xl px-3 py-2"
            value={selectValue}
            disabled={disabled}
            onChange={(e) => {
                const raw = e.target.value;
                if (raw === "") onChange(undefined);
                else if (/^[1-5]$/.test(raw)) onChange(Number(raw));
                else onChange(raw);
            }}
        >
            <option value="">—</option>
            {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                    {n}
                </option>
            ))}
            {specialOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
            ))}
        </select>
    );
}

export default function AdaptationQuestionFields({ questions, values, onChange, coreHistory, disabled }) {
    const visible = (questions || []).filter((q) => isQuestionVisible(q, values, coreHistory));
    return (
        <>
            {visible.map((q) => {
                const current = values[q.id];
                return (
                    <label key={q.id} className="block text-sm" data-testid={`q-${q.id}`}>
                        <span className="text-slate-700">
                            {q.text}
                            {q.required === false ? <span className="text-slate-400"> (необязательно)</span> : null}
                        </span>
                        {q.hint ? <small className="block text-slate-400 mt-0.5">{q.hint}</small> : null}
                        {q.type === "scale_1_5" || q.type === "scale_na" || q.type === "scale_obs" ? (
                            <ScaleSelect
                                value={current}
                                onChange={(v) => onChange(q.id, v)}
                                disabled={disabled}
                                specialOptions={q.special_options || []}
                            />
                        ) : q.type === "choice" ? (
                            <select
                                className="mt-1 w-full border rounded-xl px-3 py-2"
                                value={current ?? ""}
                                disabled={disabled}
                                onChange={(e) => onChange(q.id, e.target.value)}
                            >
                                <option value="">—</option>
                                {(q.options || []).map((opt) => (
                                    <option key={opt} value={opt}>
                                        {opt}
                                    </option>
                                ))}
                            </select>
                        ) : q.type === "multi" ? (
                            <div className="mt-2 space-y-1">
                                {(q.options || []).map((opt) => {
                                    const selected = Array.isArray(current) ? current.includes(opt) : false;
                                    return (
                                        <label key={opt} className="flex items-center gap-2 text-sm">
                                            <input
                                                type="checkbox"
                                                disabled={disabled}
                                                checked={selected}
                                                onChange={(e) => {
                                                    const prev = Array.isArray(current) ? current : [];
                                                    const exclusive = new Set(q.exclusive_options || []);
                                                    let next;
                                                    if (!e.target.checked) {
                                                        next = prev.filter((x) => x !== opt);
                                                    } else if (exclusive.has(opt)) {
                                                        next = [opt];
                                                    } else {
                                                        next = [...prev.filter((x) => !exclusive.has(x)), opt];
                                                    }
                                                    onChange(
                                                        q.id,
                                                        [...new Set(next)]
                                                    );
                                                }}
                                            />
                                            {opt}
                                        </label>
                                    );
                                })}
                            </div>
                        ) : (
                            <textarea
                                className="mt-1 w-full border rounded-xl px-3 py-2"
                                rows={3}
                                disabled={disabled}
                                value={current || ""}
                                onChange={(e) => onChange(q.id, e.target.value)}
                            />
                        )}
                    </label>
                );
            })}
        </>
    );
}
