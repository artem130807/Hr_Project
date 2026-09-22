import { useEffect, useMemo, useState } from "react";
import { loadCandidateVacancyTitle, sendProfessionalTestToCandidate } from "../../services/candidateApi";
import { getTests } from "../../services/testApi";
import { useAlertContext } from "../../context/AlertContext";
import { relationVacancyName } from "../../utils/candidateMapper";

export default function ExerciseModal({ candidate, onClose, onSuccess }) {
    const [professionalTests, setProfessionalTests] = useState([]);
    const [testsLoading, setTestsLoading] = useState(false);
    const [selectedTestId, setSelectedTestId] = useState("");
    const [message, setMessage] = useState("");
    const [sending, setSending] = useState(false);
    const [fetchedVacancyTitle, setFetchedVacancyTitle] = useState("");
    const { showAlert } = useAlertContext();

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setTestsLoading(true);
            try {
                const all = await getTests();
                const list = (Array.isArray(all) ? all : []).filter((t) => {
                    const type = String(t?.test_type || "").trim().toLowerCase();
                    return type === "вопросно-ответная форма" || type === "questions";
                });
                if (!cancelled) setProfessionalTests(list);
            } catch (e) {
                if (!cancelled) {
                    setProfessionalTests([]);
                    showAlert(`Не удалось загрузить тесты: ${e?.message || e}`, "error");
                }
            } finally {
                if (!cancelled) setTestsLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        let cancelled = false;
        setFetchedVacancyTitle("");
        if (!candidate?.id) return undefined;
        (async () => {
            try {
                const title = await loadCandidateVacancyTitle(candidate.id);
                if (!cancelled && title) setFetchedVacancyTitle(title);
            } catch (_) {
                /* keep title from candidate payload */
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [candidate?.id]);

    const vacancyTitle = useMemo(
        () =>
            fetchedVacancyTitle
            || relationVacancyName(candidate)
            || candidate?.vacancy_name
            || candidate?.last_vacancy_title
            || candidate?.position
            || "Вакансия не указана",
        [candidate, fetchedVacancyTitle]
    );

    const handleSend = async () => {
        const testId = Number(selectedTestId);
        if (!candidate?.id) return;
        if (!Number.isFinite(testId) || testId <= 0) {
            showAlert("Выберите профессиональный тест", "warning");
            return;
        }

        try {
            setSending(true);
            const resp = await sendProfessionalTestToCandidate(
                candidate.id,
                testId,
                message.trim() ? message.trim() : null
            );
            if (resp?.delivery && resp.delivery !== "sent" && resp.delivery !== "ok") {
                showAlert(
                    resp?.warning || "Тест привязан к кандидату, но HH пока не принял отправку сообщения.",
                    "warning"
                );
            } else {
                showAlert("Профессиональный тест отправлен кандидату в HH", "success");
            }
            onSuccess?.();
            onClose?.();
        } catch (e) {
            showAlert(`Ошибка отправки теста: ${e?.message || e}`, "error");
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-slate-900/55 backdrop-blur-[2px] flex items-center justify-center p-4">
            <div className="w-full max-w-2xl rounded-2xl bg-white border border-slate-200 shadow-2xl overflow-hidden">
                <div className="px-6 py-5 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
                    <h3 className="text-xl font-semibold text-slate-900">Отправить профессиональный тест</h3>
                    <p className="text-sm text-slate-500 mt-1">
                        Тест будет отправлен кандидату в личные сообщения HH.ru
                    </p>
                </div>

                <div className="p-6 space-y-5">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-sm text-slate-600">
                            Кандидат: <span className="font-medium text-slate-900">{candidate?.full_name || "—"}</span>
                        </p>
                        <p className="text-sm text-slate-600 mt-1">
                            Вакансия: <span className="font-medium text-slate-900">{vacancyTitle}</span>
                        </p>
                    </div>

                    <label className="block">
                        <span className="text-sm font-medium text-slate-700">Профессиональный тест *</span>
                        <select
                            aria-label="Профессиональный тест"
                            value={selectedTestId}
                            onChange={(e) => setSelectedTestId(e.target.value)}
                            disabled={testsLoading || sending}
                            className="mt-1.5 w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300"
                        >
                            <option value="">Выберите тест</option>
                            {professionalTests.map((test) => (
                                <option key={test.id} value={test.id}>
                                    {test.name}
                                </option>
                            ))}
                        </select>
                    </label>

                    <label className="block">
                        <span className="text-sm font-medium text-slate-700">Текст сообщения (необязательно)</span>
                        <textarea
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            rows={4}
                            placeholder="Если оставить пустым, будет отправлен стандартный текст со ссылкой на тест."
                            className="mt-1.5 w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-y"
                        />
                    </label>

                    {testsLoading ? (
                        <p className="text-xs text-slate-400">Загрузка тестов…</p>
                    ) : professionalTests.length === 0 ? (
                        <p className="text-xs text-amber-700 rounded-lg border border-amber-200 bg-amber-50 p-2.5">
                            Нет доступных профессиональных тестов типа «Вопросно-ответная форма».
                        </p>
                    ) : null}
                </div>

                <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-end gap-2">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={sending}
                        className="px-4 py-2 rounded-xl border border-slate-200 text-sm text-slate-600 hover:bg-white"
                    >
                        Отмена
                    </button>
                    <button
                        type="button"
                        onClick={handleSend}
                        disabled={sending || testsLoading || !selectedTestId}
                        className="px-4 py-2 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
                    >
                        {sending ? "Отправка..." : "Отправить тест"}
                    </button>
                </div>
            </div>
        </div>
    );
}