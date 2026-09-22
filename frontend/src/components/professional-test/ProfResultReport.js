import { useState } from "react";
import { printProfessionalResultPdf } from "../../utils/printPdf";

export function formatProfAnswer(raw) {
    if (raw == null) return { value: "", meta: null };
    if (typeof raw === "string" || typeof raw === "number") {
        return { value: String(raw), meta: null };
    }
    if (typeof raw !== "object") return { value: String(raw), meta: null };
    const value =
        raw.value != null && String(raw.value).trim()
            ? String(raw.value)
            : raw.option_index != null
              ? `Вариант #${Number(raw.option_index) + 1}`
              : "—";
    return {
        value,
        meta: {
            isCorrect: raw.is_correct,
            forced: Boolean(raw.forced_incorrect || (raw.violations || []).length),
            violations: Array.isArray(raw.violations) ? raw.violations : [],
        },
    };
}

function formatTakenAt(value) {
    if (!value) return "—";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString("ru-RU");
}

export default function ProfResultReport({ result, onClose }) {
    const answerEntries = Object.entries(result?.answers || {});
    const takenLabel = formatTakenAt(result?.taken_at);
    const hasScore = result?.score != null && result?.max_score != null;
    const passed = hasScore && Number(result.score) >= Number(result.max_score) && !result.timed_out;
    const [savingPdf, setSavingPdf] = useState(false);

    const handleSavePdf = async (event) => {
        const root = event.currentTarget.closest(".prof-result-print-root");
        try {
            setSavingPdf(true);
            await printProfessionalResultPdf({
                root,
                fullName: result.full_name,
                testName: result.test_name,
                takenAt: result.taken_at,
            });
        } catch (err) {
            window.alert(`Не удалось сохранить PDF: ${err?.message || err}`);
        } finally {
            setSavingPdf(false);
        }
    };

    return (
        <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-6 my-4 prof-result-print-root"
            onClick={(e) => e.stopPropagation()}
        >
            <div className="flex justify-between items-start gap-4 mb-4">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                        Профессиональный тест
                    </p>
                    <h2 className="text-2xl font-bold text-slate-900">{result.full_name}</h2>
                    <p className="text-sm text-slate-500 mt-1">
                        {result.position} · {takenLabel}
                        {result.test_name ? ` · ${result.test_name}` : ""}
                    </p>
                </div>
                <div className="flex items-center gap-2 shrink-0 prof-result-print-hide">
                    <button
                        type="button"
                        data-testid="prof-save-pdf"
                        disabled={savingPdf}
                        onClick={handleSavePdf}
                        className="text-sm px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 font-semibold text-slate-800"
                    >
                        {savingPdf ? "Сохранение…" : "Сохранить PDF"}
                    </button>
                    <button
                        type="button"
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-700 px-2 py-2"
                    >
                        Закрыть
                    </button>
                </div>
            </div>
            <div className="space-y-4" data-testid="prof-result-answers">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm pdf-kpi-grid">
                    <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
                        <div className="text-xs text-slate-400 uppercase">Балл</div>
                        <div className="font-semibold text-slate-800 mt-1" data-testid="prof-result-score">
                            {hasScore ? `${result.score} / ${result.max_score}` : "—"}
                        </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
                        <div className="text-xs text-slate-400 uppercase">Итог</div>
                        <div className="font-semibold text-slate-800 mt-1">
                            {!hasScore ? "—" : passed ? "Сдан" : "Не сдан"}
                        </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
                        <div className="text-xs text-slate-400 uppercase">Таймер</div>
                        <div className="font-semibold text-slate-800 mt-1">
                            {result.timed_out ? "Истёк" : "Ок"}
                        </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
                        <div className="text-xs text-slate-400 uppercase">Нарушения</div>
                        <div className="font-semibold text-slate-800 mt-1" data-testid="prof-result-integrity">
                            {result.integrity
                                ? `вкладка ${result.integrity.tab_blur_count ?? 0}, курсор ${result.integrity.mouse_leave_count ?? 0}`
                                : "—"}
                        </div>
                    </div>
                </div>
                {answerEntries.length === 0 ? (
                    <p className="text-sm text-slate-500">Ответов нет.</p>
                ) : (
                    answerEntries.map(([qid, raw]) => {
                        const { value, meta } = formatProfAnswer(raw);
                        return (
                            <div
                                key={qid}
                                className="rounded-xl border border-slate-100 bg-slate-50/60 p-4"
                            >
                                <div className="flex items-center justify-between gap-2 mb-1">
                                    <div className="text-xs font-semibold text-slate-400">
                                        Вопрос #{qid}
                                    </div>
                                    {meta?.isCorrect === true && (
                                        <span className="text-[10px] font-bold uppercase text-emerald-700">
                                            верно
                                        </span>
                                    )}
                                    {(meta?.isCorrect === false || meta?.forced) && (
                                        <span className="text-[10px] font-bold uppercase text-rose-700">
                                            {meta.forced ? "нарушение / неверно" : "неверно"}
                                        </span>
                                    )}
                                </div>
                                <p className="text-sm text-slate-800 whitespace-pre-wrap">{value}</p>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
