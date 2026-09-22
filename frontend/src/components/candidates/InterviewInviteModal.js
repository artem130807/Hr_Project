import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import {
    DEFAULT_INTERVIEW_CONTACT_NAME,
    DEFAULT_INTERVIEW_CONTACT_PHONE,
    DEFAULT_INTERVIEW_FORMAT,
    addHourToTime,
    buildInterviewInviteText,
    CANDIDATE_INTERVIEW_REMINDER_QUESTION,
    buildCandidateInterviewReminderText,
    candidateReminderAtIso,
    defaultCandidateReminderAt,
} from "../../utils/interviewInvite";

export default function InterviewInviteModal({
    open,
    candidate,
    defaultDate = "",
    defaultTime = "",
    lockSchedule = false,
    onClose,
    onSubmit,
}) {
    const { user } = useAuth() || {};
    const [dateValue, setDateValue] = useState(defaultDate || "");
    const [timeValue, setTimeValue] = useState(String(defaultTime || "").slice(0, 5));
    const [format, setFormat] = useState(DEFAULT_INTERVIEW_FORMAT);
    const [contactPhone, setContactPhone] = useState(DEFAULT_INTERVIEW_CONTACT_PHONE);
    const [contactName, setContactName] = useState(user?.name || DEFAULT_INTERVIEW_CONTACT_NAME);
    const [text, setText] = useState("");
    const [dirty, setDirty] = useState(false);
    const [remindCandidate, setRemindCandidate] = useState(false);
    const [remindAt, setRemindAt] = useState("");
    const [reminderText, setReminderText] = useState("");
    const [reminderDirty, setReminderDirty] = useState(false);
    const [loading, setLoading] = useState(false);
    const textareaRef = useRef(null);

    useEffect(() => {
        if (!open) return;
        setDateValue(defaultDate || "");
        setTimeValue(String(defaultTime || "").slice(0, 5));
        setFormat(DEFAULT_INTERVIEW_FORMAT);
        setContactPhone(DEFAULT_INTERVIEW_CONTACT_PHONE);
        setContactName(user?.name || DEFAULT_INTERVIEW_CONTACT_NAME);
        setDirty(false);
        setRemindCandidate(false);
        setRemindAt("");
        setReminderText("");
        setReminderDirty(false);
        setText(
            buildInterviewInviteText({
                fullName: candidate?.full_name,
                format: DEFAULT_INTERVIEW_FORMAT,
                dateValue: defaultDate || "",
                timeValue: String(defaultTime || "").slice(0, 5),
                contactPhone: DEFAULT_INTERVIEW_CONTACT_PHONE,
                contactName: user?.name || DEFAULT_INTERVIEW_CONTACT_NAME,
            })
        );
        setTimeout(() => textareaRef.current?.focus(), 0);
    }, [open, candidate?.full_name, defaultDate, defaultTime, user?.name]);

    useEffect(() => {
        if (!open || dirty) return;
        setText(
            buildInterviewInviteText({
                fullName: candidate?.full_name,
                format,
                dateValue,
                timeValue,
                contactPhone,
                contactName,
            })
        );
    }, [open, dirty, candidate?.full_name, format, dateValue, timeValue, contactPhone, contactName]);

    useEffect(() => {
        if (!open || !remindCandidate || reminderDirty) return;
        setRemindAt(defaultCandidateReminderAt(dateValue, timeValue));
        setReminderText(
            buildCandidateInterviewReminderText({
                fullName: candidate?.full_name,
                dateValue,
                timeValue,
                format,
            })
        );
    }, [open, remindCandidate, reminderDirty, candidate?.full_name, dateValue, timeValue, format]);

    if (!open) return null;

    const handleSubmit = async () => {
        const val = text.trim();
        if (!val || !dateValue || !String(timeValue || "").trim()) return;
        if (remindCandidate && (!String(remindAt || "").trim() || !reminderText.trim())) return;
        try {
            setLoading(true);
            await onSubmit?.(val, {
                date: dateValue,
                startTime: String(timeValue).slice(0, 5),
                endTime: addHourToTime(timeValue),
            }, remindCandidate ? {
                enabled: true,
                remind_at: candidateReminderAtIso(remindAt),
                message: reminderText.trim(),
            } : null);
        } finally {
            setLoading(false);
        }
    };

    const canSend =
        Boolean(text.trim() && dateValue && String(timeValue || "").trim()) &&
        (!remindCandidate || Boolean(String(remindAt || "").trim() && reminderText.trim()));

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 no-click-open">
            <div
                className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
                onClick={() => (!loading ? onClose?.() : null)}
            />
            <div
                className="relative z-10 flex w-full max-w-xl max-h-[calc(100vh-2rem)] flex-col bg-white rounded-2xl shadow-2xl ring-1 ring-slate-900/5 overflow-hidden"
                data-testid="interview-invite-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="interview-invite-title"
            >
                <div className="shrink-0 px-6 py-4 border-b border-slate-100">
                    <h3 id="interview-invite-title" className="text-lg font-semibold text-slate-900">
                        Пригласить на собеседование
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                        Текст уйдёт кандидату в сообщения hh.ru. Проверьте дату, контакты и формулировку.
                    </p>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-6 space-y-4" data-testid="interview-invite-body">
                    <div className="grid grid-cols-2 gap-3">
                        <label className="block text-sm">
                            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Дата *</span>
                            <input
                                type="date"
                                className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                                value={dateValue}
                                onChange={(e) => setDateValue(e.target.value)}
                                disabled={loading || lockSchedule}
                                data-testid="interview-date"
                            />
                        </label>
                        <label className="block text-sm">
                            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Время *</span>
                            <input
                                type="time"
                                className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                                value={timeValue}
                                onChange={(e) => setTimeValue(e.target.value)}
                                disabled={loading || lockSchedule}
                                data-testid="interview-time"
                            />
                        </label>
                    </div>
                    <label className="block text-sm">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Формат</span>
                        <select
                            className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                            value={format}
                            onChange={(e) => setFormat(e.target.value)}
                            disabled={loading}
                        >
                            <option value="очный">очный</option>
                            <option value="онлайн">онлайн</option>
                            <option value="телефонный">телефонный</option>
                        </select>
                    </label>
                    <label className="block text-sm">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Контактный телефон</span>
                        <input
                            className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                            value={contactPhone}
                            onChange={(e) => setContactPhone(e.target.value)}
                            disabled={loading}
                        />
                    </label>
                    <label className="block text-sm">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Контактное лицо</span>
                        <input
                            className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                            value={contactName}
                            onChange={(e) => setContactName(e.target.value)}
                            disabled={loading}
                        />
                    </label>
                    <label className="block">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-2 block">
                            Текст письма
                        </span>
                        <textarea
                            ref={textareaRef}
                            className="w-full min-h-[120px] max-h-48 border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/40 focus:border-[#4f46e5]"
                            value={text}
                            onChange={(e) => {
                                setDirty(true);
                                setText(e.target.value);
                            }}
                            data-testid="interview-letter"
                        />
                    </label>
                    <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                        <input
                            type="checkbox"
                            className="mt-1"
                            checked={remindCandidate}
                            onChange={(e) => {
                                const on = e.target.checked;
                                setRemindCandidate(on);
                                setReminderDirty(false);
                                if (on) {
                                    setRemindAt(defaultCandidateReminderAt(dateValue, timeValue));
                                    setReminderText(
                                        buildCandidateInterviewReminderText({
                                            fullName: candidate?.full_name,
                                            dateValue,
                                            timeValue,
                                            format,
                                        })
                                    );
                                }
                            }}
                            disabled={loading}
                            data-testid="candidate-reminder-toggle"
                        />
                        <span className="text-sm text-slate-700">
                            {CANDIDATE_INTERVIEW_REMINDER_QUESTION}
                            <span className="block text-xs text-slate-500 mt-1">
                                Если да — укажите, когда отправить кандидату сообщение в чат hh.ru.
                            </span>
                        </span>
                    </label>
                    {remindCandidate ? (
                        <div className="space-y-3 rounded-xl border border-sky-100 bg-sky-50/60 p-3" data-testid="candidate-reminder-fields">
                            <label className="block text-sm">
                                <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
                                    Когда отправить напоминание *
                                </span>
                                <input
                                    type="datetime-local"
                                    step="1"
                                    className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white"
                                    value={remindAt}
                                    onChange={(e) => {
                                        setReminderDirty(true);
                                        setRemindAt(e.target.value);
                                    }}
                                    disabled={loading}
                                    data-testid="candidate-reminder-at"
                                />
                            </label>
                            <label className="block">
                                <span className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-2 block">
                                    Текст напоминания кандидату
                                </span>
                                <textarea
                                    className="w-full min-h-[88px] max-h-40 border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 bg-white"
                                    value={reminderText}
                                    onChange={(e) => {
                                        setReminderDirty(true);
                                        setReminderText(e.target.value);
                                    }}
                                    data-testid="candidate-reminder-text"
                                />
                            </label>
                        </div>
                    ) : null}
                </div>
                <div className="shrink-0 flex justify-end gap-2 px-6 py-4 border-t border-slate-100 bg-white">
                    <button
                        type="button"
                        className="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 text-sm font-medium"
                        onClick={() => (!loading ? onClose?.() : null)}
                        disabled={loading}
                    >
                        Отмена
                    </button>
                    <button
                        type="button"
                        className="px-4 py-2 rounded-xl bg-sky-700 text-white hover:bg-sky-800 text-sm font-semibold disabled:opacity-60"
                        onClick={handleSubmit}
                        disabled={loading || !canSend}
                        data-testid="interview-send"
                    >
                        {loading ? "Отправка…" : "Отправить приглашение"}
                    </button>
                </div>
            </div>
        </div>
    );
}
