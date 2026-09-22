import { useEffect, useState } from "react";
import { getCandidate, loadCandidateVacancyTitle } from "../../services/candidateApi";
import { createEvent, searchEventEmployees } from "../../services/eventsApi";
import { useAlertContext } from "../../context/AlertContext";
import { formatTelegramUsername, relationVacancyName } from "../../utils/candidateMapper";
import {
    buildInterviewReminderFormState,
    buildInterviewReminderNote,
    interviewTimeRange,
} from "../../utils/interviewReminder";
import { normalizeRemindBefore } from "../events/remindBefore";

export default function InterviewReminderModal({
    open,
    candidate,
    date,
    startTime,
    endTime,
    onClose,
    onSkip,
    onSaved,
}) {
    const { showAlert } = useAlertContext();
    const [form, setForm] = useState(null);
    const [loadingForm, setLoadingForm] = useState(false);
    const [saving, setSaving] = useState(false);
    const [hrQuery, setHrQuery] = useState("");
    const [hrSuggestions, setHrSuggestions] = useState([]);
    const [hrSearching, setHrSearching] = useState(false);
    const [hrPickedFromErp, setHrPickedFromErp] = useState(false);

    useEffect(() => {
        if (!open || !candidate?.id) {
            setForm(null);
            setLoadingForm(false);
            setHrQuery("");
            setHrSuggestions([]);
            setHrPickedFromErp(false);
            return undefined;
        }
        let cancelled = false;
        const snapshot = candidate;
        setLoadingForm(true);
        (async () => {
            try {
                let full = { ...snapshot };
                try {
                    const fresh = await getCandidate(snapshot.id);
                    if (fresh && typeof fresh === "object") full = { ...full, ...fresh };
                } catch (_) {
                    /* keep payload from the invite */
                }
                let vacancyName =
                    relationVacancyName(full)
                    || full.vacancy_name
                    || full.last_vacancy_title
                    || "";
                try {
                    vacancyName = (await loadCandidateVacancyTitle(snapshot.id)) || vacancyName;
                } catch (_) {
                    /* keep title from candidate */
                }
                if (cancelled) return;
                setForm(
                    buildInterviewReminderFormState({
                        candidateName: full.full_name || `Кандидат #${snapshot.id}`,
                        vacancyName,
                        eventDate: date,
                        interviewTime: interviewTimeRange(startTime, endTime),
                        remindAtTime: String(startTime || "").slice(0, 5),
                        candidatePhone: full.phone_number || full.phone || "",
                        candidateEmail: full.email || "",
                        candidateTelegram: formatTelegramUsername(full.telegram_username) || "",
                    })
                );
                setHrQuery("");
                setHrSuggestions([]);
                setHrPickedFromErp(false);
            } finally {
                if (!cancelled) setLoadingForm(false);
            }
        })();
        return () => {
            cancelled = true;
        };
        // Prefill from the candidate snapshot passed by the invite/booking flow.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, candidate?.id, date, startTime, endTime]);

    useEffect(() => {
        if (!open || loadingForm) return undefined;
        const q = String(hrQuery || "").trim();
        if (q.length < 2) {
            setHrSuggestions([]);
            setHrSearching(false);
            return undefined;
        }
        let cancelled = false;
        setHrSearching(true);
        const timer = setTimeout(async () => {
            try {
                const rows = await searchEventEmployees(q, { by: "name", limit: 15 });
                if (!cancelled) setHrSuggestions(Array.isArray(rows) ? rows : []);
            } catch {
                if (!cancelled) setHrSuggestions([]);
            } finally {
                if (!cancelled) setHrSearching(false);
            }
        }, 250);
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [hrQuery, open, loadingForm]);

    const updateField = (patch) => {
        setForm((prev) => {
            if (!prev) return prev;
            const next = { ...prev, ...patch };
            next.note = buildInterviewReminderNote({
                candidateName: next.candidate_name,
                vacancyName: next.vacancy_name,
                eventDate: next.event_date,
                interviewTime: next.interview_time,
                candidatePhone: next.candidate_phone,
                candidateEmail: next.candidate_email,
                candidateTelegram: next.candidate_telegram,
            });
            return next;
        });
    };

    const handleSave = async () => {
        if (!form) return;
        if (!String(form.candidate_name || "").trim()) {
            showAlert("Укажите кандидата для события собеседования", "error");
            return;
        }
        if (!form.event_date) {
            showAlert("Укажите дату собеседования", "error");
            return;
        }
        if (!String(form.interview_time || "").trim()) {
            showAlert("Укажите время собеседования", "error");
            return;
        }
        if (!hrPickedFromErp || !String(form.telegram_user || "").trim()) {
            showAlert("Выберите Telegram сотрудника из ERP-подсказок", "error");
            return;
        }
        try {
            setSaving(true);
            await createEvent({
                type: "interview",
                employee_name: null,
                event_date: form.event_date,
                remind_before: normalizeRemindBefore(form.remind_before, 1),
                remind_at_time: String(form.remind_at_time || "").trim() || null,
                telegram_user: String(form.telegram_user || "").trim() || null,
                note: String(form.note || "").trim() || null,
            });
            showAlert("Напоминание о собеседовании сохранено", "success");
            if (onSaved) onSaved();
            else onClose?.();
        } catch (e) {
            showAlert(`Ошибка сохранения напоминания: ${e.message || e}`, "error");
        } finally {
            setSaving(false);
        }
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[120] bg-black bg-opacity-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl">
                <h3 className="text-xl font-bold mb-4">Напоминание о собеседовании</h3>
                {loadingForm || !form ? (
                    <p className="text-sm text-slate-500">Подтягиваем данные кандидата…</p>
                ) : (
                    <div className="space-y-3 mb-4" data-testid="interview-reminder-form">
                        <label className="block text-sm">
                            <span className="text-slate-600">Кандидат</span>
                            <input
                                className="mt-1 w-full border rounded p-2"
                                value={form.candidate_name}
                                onChange={(e) => updateField({ candidate_name: e.target.value })}
                            />
                        </label>
                        <label className="block text-sm">
                            <span className="text-slate-600">Вакансия</span>
                            <input
                                className="mt-1 w-full border rounded p-2"
                                value={form.vacancy_name}
                                onChange={(e) => updateField({ vacancy_name: e.target.value })}
                            />
                        </label>
                        <div className="grid grid-cols-2 gap-3">
                            <label className="block text-sm">
                                <span className="text-slate-600">Дата собеседования</span>
                                <input
                                    type="date"
                                    className="mt-1 w-full border rounded p-2"
                                    value={form.event_date}
                                    onChange={(e) => updateField({ event_date: e.target.value })}
                                />
                            </label>
                            <label className="block text-sm">
                                <span className="text-slate-600">Время собеседования</span>
                                <input
                                    className="mt-1 w-full border rounded p-2"
                                    value={form.interview_time}
                                    onChange={(e) => updateField({ interview_time: e.target.value })}
                                />
                            </label>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <label className="block text-sm">
                                <span className="text-slate-600">Напомнить за (дней)</span>
                                <input
                                    type="number"
                                    min="0"
                                    className="mt-1 w-full border rounded p-2"
                                    value={form.remind_before}
                                    onChange={(e) => setForm((prev) => ({ ...prev, remind_before: e.target.value }))}
                                />
                            </label>
                            <label className="block text-sm">
                                <span className="text-slate-600">Напомнить во сколько</span>
                                <input
                                    type="time"
                                    className="mt-1 w-full border rounded p-2"
                                    value={form.remind_at_time}
                                    onChange={(e) => setForm((prev) => ({ ...prev, remind_at_time: e.target.value }))}
                                />
                            </label>
                        </div>
                        <label className="block text-sm">
                            <span className="text-slate-600">Telegram сотрудника</span>
                            <input
                                className="mt-1 w-full border rounded p-2"
                                value={hrQuery}
                                onChange={(e) => {
                                    setHrQuery(e.target.value);
                                    setHrPickedFromErp(false);
                                }}
                                placeholder="Начните вводить ФИО сотрудника"
                            />
                            {hrSearching && <p className="text-xs text-slate-400 mt-1">Поиск в ERP...</p>}
                            {!hrSearching && hrSuggestions.length > 0 && (
                                <div className="mt-1 border border-slate-200 rounded-lg max-h-40 overflow-auto">
                                    {hrSuggestions.map((item) => (
                                        <button
                                            key={item.erp_user_id}
                                            type="button"
                                            className="block w-full text-left px-3 py-2 text-sm hover:bg-slate-50 border-b last:border-b-0"
                                            onClick={() => {
                                                setHrQuery(item.full_name || "");
                                                setForm((prev) => ({
                                                    ...prev,
                                                    telegram_user: item.tg_username || "",
                                                }));
                                                setHrSuggestions([]);
                                                setHrPickedFromErp(true);
                                            }}
                                        >
                                            <div className="font-medium text-slate-900">{item.full_name || "—"}</div>
                                            <div className="text-xs text-slate-500">{item.tg_username || "без telegram"}</div>
                                        </button>
                                    ))}
                                </div>
                            )}
                            {form.telegram_user && (
                                <p className="text-xs text-slate-500 mt-1">
                                    Выбран Telegram сотрудника: <span className="font-medium">{form.telegram_user}</span>
                                </p>
                            )}
                        </label>
                        <label className="block text-sm">
                            <span className="text-slate-600">Заметка</span>
                            <textarea
                                rows={3}
                                className="mt-1 w-full border rounded p-2"
                                value={form.note}
                                onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))}
                            />
                        </label>
                    </div>
                )}
                <div className="flex gap-3 justify-end flex-wrap">
                    <button
                        type="button"
                        onClick={onClose}
                        className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                        disabled={saving}
                    >
                        Отмена
                    </button>
                    <button
                        type="button"
                        onClick={() => (onSkip || onClose)?.()}
                        disabled={saving}
                        className="px-4 py-2 border border-slate-300 text-slate-700 rounded hover:bg-slate-50"
                    >
                        Пропустить
                    </button>
                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={saving || loadingForm || !form}
                        className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400"
                    >
                        {saving ? "Сохранение..." : "Сохранить напоминание"}
                    </button>
                </div>
            </div>
        </div>
    );
}
