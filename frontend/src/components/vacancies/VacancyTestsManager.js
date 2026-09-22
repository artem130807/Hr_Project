import { useState, useEffect, useCallback } from "react";
import { getTests, getTestForVacancy, updateTestForVacancy } from "../../services/testApi";
import { useAlertContext } from "../../context/AlertContext";

function normalizeIdList(payload) {
    const raw = Array.isArray(payload)
        ? payload
        : payload?.items || payload?.data || payload?.test_ids || [];
    return (Array.isArray(raw) ? raw : [])
        .map((t) => (typeof t === "object" && t != null ? t.id ?? t.test_id : t))
        .map(Number)
        .filter((id) => Number.isFinite(id) && id > 0);
}

function normalizeTests(payload) {
    const raw = Array.isArray(payload) ? payload : payload?.items || payload?.data || [];
    return (Array.isArray(raw) ? raw : []).filter((t) => t?.id != null);
}

/**
 * Modal: bind Q&A / URL tests to a vacancy (VacancyTestRelation).
 */
export default function VacancyTestsManager({ vacancyId, vacancyName, onClose }) {
    const [allTests, setAllTests] = useState([]);
    const [selectedTestIds, setSelectedTestIds] = useState([]);
    const [initialIds, setInitialIds] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const { showAlert } = useAlertContext();

    const titleName = vacancyName || (vacancyId != null ? `#${vacancyId}` : "вакансии");

    const loadData = useCallback(async () => {
        if (vacancyId == null) return;
        try {
            setLoading(true);
            const [tests, vacancyTests] = await Promise.all([
                getTests(),
                getTestForVacancy(vacancyId),
            ]);
            const normalizedTests = normalizeTests(tests);
            const ids = normalizeIdList(vacancyTests);
            setAllTests(normalizedTests);
            setSelectedTestIds(ids);
            setInitialIds(ids);
        } catch (e) {
            console.error("Ошибка загрузки тестов вакансии", e);
            showAlert(`Не удалось загрузить тесты: ${e.message || e}`, "error");
            setAllTests([]);
            setSelectedTestIds([]);
            setInitialIds([]);
        } finally {
            setLoading(false);
        }
    }, [vacancyId, showAlert]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    useEffect(() => {
        const onKey = (e) => {
            if (e.key === "Escape" && !saving) onClose?.();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [onClose, saving]);

    const handleToggle = (testId) => {
        const id = Number(testId);
        setSelectedTestIds((prev) =>
            prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
        );
    };

    const dirty =
        selectedTestIds.length !== initialIds.length ||
        selectedTestIds.some((id) => !initialIds.includes(id));

    const handleSave = async () => {
        if (vacancyId == null) return;
        try {
            setSaving(true);
            await updateTestForVacancy(vacancyId, selectedTestIds);
            showAlert(
                selectedTestIds.length
                    ? `Привязано тестов: ${selectedTestIds.length}`
                    : "Все тесты отвязаны от вакансии",
                "success"
            );
            onClose?.();
        } catch (e) {
            console.error("Ошибка сохранения тестов вакансии", e);
            showAlert(`Не удалось сохранить: ${e.message || e}`, "error");
        } finally {
            setSaving(false);
        }
    };

    const handleBackdrop = (e) => {
        if (e.target === e.currentTarget && !saving) onClose?.();
    };

    return (
        <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-start z-[60] overflow-y-auto py-8 px-4"
            onClick={handleBackdrop}
            data-testid="vacancy-tests-modal"
        >
            <div
                className="bg-white p-6 rounded-2xl shadow-xl w-full max-w-2xl ring-1 ring-slate-900/5"
                role="dialog"
                aria-modal="true"
                aria-labelledby="vacancy-tests-title"
            >
                <div className="flex items-start justify-between gap-4 mb-5">
                    <div>
                        <h2
                            id="vacancy-tests-title"
                            className="text-xl font-bold text-slate-900"
                        >
                            Тесты для вакансии «{titleName}»
                        </h2>
                        <p className="mt-1 text-sm text-slate-500">
                            Отметьте тесты, которые кандидат проходит по этой вакансии.
                            Можно снять все галочки, чтобы отвязать тесты.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => !saving && onClose?.()}
                        className="shrink-0 w-9 h-9 rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-800 transition-colors flex items-center justify-center"
                        aria-label="Закрыть"
                        data-testid="vacancy-tests-close"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {loading ? (
                    <div className="py-12 text-center text-slate-400 text-sm flex items-center justify-center gap-2">
                        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                            <circle
                                className="opacity-25"
                                cx="12"
                                cy="12"
                                r="10"
                                stroke="currentColor"
                                strokeWidth="4"
                                fill="none"
                            />
                            <path
                                className="opacity-75"
                                fill="currentColor"
                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                            />
                        </svg>
                        Загрузка тестов…
                    </div>
                ) : allTests.length === 0 ? (
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-8 text-center">
                        <p className="text-sm text-slate-600 font-medium">Нет доступных тестов</p>
                        <p className="mt-1 text-xs text-slate-500">
                            Создайте тест в разделе «Тесты», затем вернитесь сюда.
                        </p>
                    </div>
                ) : (
                    <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
                        {allTests.map((test) => {
                            const id = Number(test.id);
                            const checked = selectedTestIds.includes(id);
                            return (
                                <label
                                    key={id}
                                    className={`flex items-start gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-colors ${
                                        checked
                                            ? "border-[#4f46e5] bg-[#4f46e5]/10"
                                            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                                    }`}
                                    data-testid={`vacancy-test-option-${id}`}
                                >
                                    <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={() => handleToggle(id)}
                                        className="mt-1 w-4 h-4 text-[#4f46e5] border-slate-300 rounded focus:ring-[#4f46e5]"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <div className="font-medium text-slate-900 text-sm">
                                            {test.name || `Тест #${id}`}
                                        </div>
                                        {test.description ? (
                                            <p className="mt-0.5 text-xs text-slate-500 line-clamp-2">
                                                {test.description}
                                            </p>
                                        ) : null}
                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                            {test.test_type ? (
                                                <span className="px-2 py-0.5 bg-slate-50 text-slate-600 border border-slate-200/60 rounded text-[10px] font-bold uppercase tracking-wider">
                                                    {test.test_type}
                                                </span>
                                            ) : null}
                                            {test.results_type ? (
                                                <span className="px-2 py-0.5 bg-slate-50 text-slate-600 border border-slate-200/60 rounded text-[10px] font-bold uppercase tracking-wider">
                                                    {test.results_type}
                                                </span>
                                            ) : null}
                                        </div>
                                    </div>
                                </label>
                            );
                        })}
                    </div>
                )}

                <div className="flex flex-wrap items-center justify-between gap-3 pt-5 mt-5 border-t border-slate-100">
                    <p className="text-xs text-slate-500">
                        Выбрано:{" "}
                        <span className="font-semibold text-slate-700">{selectedTestIds.length}</span>
                        {allTests.length > 0 ? ` из ${allTests.length}` : ""}
                        {dirty ? (
                            <span className="ml-2 text-amber-700">· есть несохранённые изменения</span>
                        ) : null}
                    </p>
                    <div className="flex gap-2 ml-auto">
                        <button
                            type="button"
                            onClick={() => !saving && onClose?.()}
                            disabled={saving}
                            className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                            Отмена
                        </button>
                        <button
                            type="button"
                            onClick={handleSave}
                            disabled={saving || loading}
                            data-testid="vacancy-tests-save"
                            className="px-5 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {saving ? "Сохранение…" : "Сохранить"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export { normalizeIdList, normalizeTests };
