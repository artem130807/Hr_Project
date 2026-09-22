import { formatDateRu } from "../../utils/dateFormat";
import { printProfessionalTestPdf } from "../../utils/printPdf";
import { useState } from "react";

function questionText(question) {
    return question.question_text || question.text || "—";
}

function questionOptions(question) {
    return Array.isArray(question.options) ? question.options.filter((o) => String(o ?? "").trim()) : [];
}

export default function TestDetails({ test, onClose }) {
    const questions = Array.isArray(test?.questions) ? test.questions : [];
    const canPdf = Boolean(test?.name);
    const [savingPdf, setSavingPdf] = useState(false);

    const handleSavePdf = async (event) => {
        const root = event.currentTarget.closest(".prof-test-print-root");
        try {
            setSavingPdf(true);
            await printProfessionalTestPdf({ root, testName: test.name });
        } catch (err) {
            window.alert(`Не удалось сохранить PDF: ${err?.message || err}`);
        } finally {
            setSavingPdf(false);
        }
    };

    return (
        <div className="prof-test-print-root">
            <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                        Профессиональный тест
                    </p>
                    <h2 className="text-2xl font-bold mb-3 text-slate-900">{test.name}</h2>
                    <div className="flex gap-2 flex-wrap">
                        {test.test_type && (
                            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                                {test.test_type}
                            </span>
                        )}
                        {test.type && !test.test_type && (
                            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                                {test.type}
                            </span>
                        )}
                        {test.results_type && (
                            <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm font-medium">
                                {test.results_type}
                            </span>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 prof-test-print-hide">
                    {canPdf && (
                        <button
                            type="button"
                            data-testid="prof-test-save-pdf"
                            disabled={savingPdf}
                            onClick={handleSavePdf}
                            className="text-sm px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 font-semibold text-slate-800"
                        >
                            {savingPdf ? "Сохранение…" : "Сохранить PDF"}
                        </button>
                    )}
                    {onClose && (
                        <button
                            type="button"
                            onClick={onClose}
                            className="text-sm px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 font-medium text-slate-700"
                        >
                            Закрыть
                        </button>
                    )}
                </div>
            </div>

            {test.description && (
                <div className="mb-6">
                    <h3 className="font-medium text-lg mb-2">Описание</h3>
                    <p className="text-slate-700 bg-slate-50 p-4 rounded-xl whitespace-pre-wrap">{test.description}</p>
                </div>
            )}

            {test.instruction_text && (
                <div className="mb-6">
                    <h3 className="font-semibold text-lg mb-2">Инструкция по прохождению</h3>
                    <p className="text-slate-700 bg-slate-50 p-4 rounded-xl whitespace-pre-wrap">{test.instruction_text}</p>
                </div>
            )}

            {test.url && (
                <div className="mb-6">
                    <h3 className="font-semibold text-lg mb-2">Ссылка на тест</h3>
                    <a
                        href={test.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 underline font-medium"
                    >
                        Открыть внешний тест
                    </a>
                </div>
            )}

            {questions.length > 0 && (
                <div className="mb-6">
                    <h3 className="font-semibold text-lg mb-3">Вопросы теста ({questions.length})</h3>
                    <div className="space-y-4">
                        {questions.map((question, index) => {
                            const options = questionOptions(question);
                            const correct = question.correct_option_index;
                            return (
                                <div key={question.id || index} className="bg-white border border-slate-200 rounded-xl p-4">
                                    <p className="font-medium text-slate-800 mb-2">
                                        {index + 1}. {questionText(question)}
                                    </p>
                                    {options.length > 0 ? (
                                        <ol className="list-none space-y-1.5 mt-3">
                                            {options.map((opt, oi) => (
                                                <li
                                                    key={`${question.id || index}-${oi}`}
                                                    className={`text-sm px-3 py-1.5 rounded-lg border ${
                                                        correct === oi
                                                            ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                                                            : "border-slate-100 bg-slate-50 text-slate-700"
                                                    }`}
                                                >
                                                    <span className="font-semibold mr-2">{oi + 1}.</span>
                                                    {opt}
                                                    {correct === oi && (
                                                        <span className="ml-2 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
                                                            верный ответ
                                                        </span>
                                                    )}
                                                </li>
                                            ))}
                                        </ol>
                                    ) : (
                                        <p className="text-xs text-slate-400 italic mt-1">Свободный ответ</p>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {test.created_at && (
                <div className="text-sm text-slate-500 pt-4 border-t border-slate-100">
                    <p>Создан {formatDateRu(test.created_at)}</p>
                    {test.updated_at && <p>Обновлён {formatDateRu(test.updated_at)}</p>}
                </div>
            )}
        </div>
    );
}
