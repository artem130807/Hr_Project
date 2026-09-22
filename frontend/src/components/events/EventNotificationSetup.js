import React, { useEffect, useRef, useState } from "react";
import { createEvent, searchEventEmployees } from "../../services/eventsApi";
import { getCandidates, sendInterviewInvite } from "../../services/candidateApi";
import { useAlertContext } from "../../context/AlertContext";
import { useAuth } from "../../context/AuthContext";
import InterviewInviteModal from "../candidates/InterviewInviteModal";
import { EVENT_TYPE_OPTIONS, eventTypeRequiresEmployeeName, isPermanentEventType, REPEAT_INTERVAL_OPTIONS } from "./eventTypes";
import { normalizeRemindBefore } from "./remindBefore";
import { buildInterviewReminderNote } from "../../utils/interviewReminder";

const useErpDirectorySearch = (query, by) => {
    const [suggestions, setSuggestions] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [isSearching, setIsSearching] = useState(false);
    const searchSeq = useRef(0);
    const blurTimer = useRef(null);

    useEffect(() => {
        const q = String(query || "").trim().replace(/^@+/, "");
        if (q.length < 2) {
            setSuggestions([]);
            setIsSearching(false);
            return undefined;
        }

        const seq = ++searchSeq.current;
        setIsSearching(true);
        const timer = setTimeout(async () => {
            try {
                const rows = await searchEventEmployees(query, { limit: 15, by });
                if (seq !== searchSeq.current) return;
                setSuggestions(Array.isArray(rows) ? rows : []);
                setShowSuggestions(true);
            } catch {
                if (seq !== searchSeq.current) return;
                setSuggestions([]);
            } finally {
                if (seq === searchSeq.current) setIsSearching(false);
            }
        }, 250);

        return () => clearTimeout(timer);
    }, [query, by]);

    useEffect(() => () => {
        if (blurTimer.current) clearTimeout(blurTimer.current);
    }, []);

    const openIfAny = () => {
        if (suggestions.length) setShowSuggestions(true);
    };

    const scheduleClose = () => {
        blurTimer.current = setTimeout(() => setShowSuggestions(false), 150);
    };

    const clear = () => {
        setSuggestions([]);
        setShowSuggestions(false);
    };

    return {
        suggestions,
        showSuggestions,
        setShowSuggestions,
        isSearching,
        openIfAny,
        scheduleClose,
        clear,
    };
};

const SuggestionDropdown = ({
    visible,
    isSearching,
    suggestions,
    emptyText,
    onPick,
    primaryKey,
    secondaryKey,
}) => {
    if (!visible) return null;
    return (
        <div className="absolute z-20 left-0 right-0 mt-1 max-h-56 overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg">
            {isSearching && suggestions.length === 0 && (
                <div className="px-4 py-2.5 text-sm text-slate-400">Поиск…</div>
            )}
            {!isSearching && suggestions.length === 0 && (
                <div className="px-4 py-2.5 text-sm text-slate-400">{emptyText}</div>
            )}
            {suggestions.map((item) => (
                <button
                    key={item.erp_user_id}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => onPick(item)}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b border-slate-100 last:border-b-0"
                >
                    <span className="block font-medium text-slate-900">{item[primaryKey] || "—"}</span>
                    {item[secondaryKey] && (
                        <span className="block text-xs text-slate-400 truncate">{item[secondaryKey]}</span>
                    )}
                </button>
            ))}
        </div>
    );
};

const EventNotificationSetup = ({ onRefresh }) => {
    const [form, setForm] = useState({
        type: "birthday",
        employee_name: "",
        vacancy_name: "",
        child_name: "",
        telegram_user: "",
        note: "",
        event_date: "",
        interview_time: "",
        remind_before: 3,
        remind_at_time: "",
        repeat_interval_count: 1,
        repeat_interval_unit: "month",
        candidate_id: "",
        candidate_name: "",
        candidate_search: "",
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [interviewHrPicked, setInterviewHrPicked] = useState(false);
    const [candidateOptions, setCandidateOptions] = useState([]);
    const [candidatesLoading, setCandidatesLoading] = useState(false);
    const [inviteState, setInviteState] = useState(null);
    const { showAlert } = useAlertContext();
    const { user } = useAuth() || {};

    const nameSearch = useErpDirectorySearch(form.employee_name, "name");
    const tgSearch = useErpDirectorySearch(
        form.telegram_user,
        form.type === "interview" ? "name" : "telegram"
    );

    const pickNameSuggestion = (item) => {
        setForm((prev) => ({
            ...prev,
            employee_name: item.full_name || prev.employee_name,
            telegram_user: item.tg_username || prev.telegram_user,
        }));
        nameSearch.clear();
    };

    const pickTelegramSuggestion = (item) => {
        setForm((prev) => {
            const next = {
                ...prev,
                telegram_user: item.tg_username || prev.telegram_user,
            };
            if (
                eventTypeRequiresEmployeeName(prev.type)
                && !prev.employee_name.trim()
                && item.full_name
            ) {
                next.employee_name = item.full_name;
            }
            return next;
        });
        setInterviewHrPicked(true);
        tgSearch.clear();
    };

    const needsEmployeeName = eventTypeRequiresEmployeeName(form.type);
    const isInterview = form.type === "interview";
    const isPermanent = isPermanentEventType(form.type);
    const lastInterviewAutoNote = useRef("");

    useEffect(() => {
        if (!isInterview) return;
        const autoNote = buildInterviewReminderNote({
            candidateName: form.candidate_name,
            vacancyName: form.vacancy_name,
            eventDate: form.event_date,
            interviewTime: form.interview_time,
        });
        setForm((prev) => {
            const shouldReplace =
                !String(prev.note || "").trim()
                || prev.note === lastInterviewAutoNote.current;
            if (!shouldReplace) return prev;
            return { ...prev, note: autoNote };
        });
        lastInterviewAutoNote.current = autoNote;
    }, [form.event_date, form.interview_time, form.vacancy_name, form.candidate_name, isInterview]);

    useEffect(() => {
        if (!isInterview) return undefined;
        let cancelled = false;
        const timer = setTimeout(async () => {
            try {
                setCandidatesLoading(true);
                const data = await getCandidates(
                    null,
                    String(form.candidate_search || "").trim() || null,
                    null,
                    null,
                    undefined,
                    0,
                    50
                );
                if (cancelled) return;
                const items = Array.isArray(data) ? data : (data?.items ?? []);
                setCandidateOptions(items);
            } catch {
                if (!cancelled) setCandidateOptions([]);
            } finally {
                if (!cancelled) setCandidatesLoading(false);
            }
        }, form.candidate_search ? 300 : 0);
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [form.candidate_search, isInterview]);

    const submit = async (e) => {
        e.preventDefault();
        if (!form.event_date) {
            showAlert("Укажите дату", "error");
            return;
        }
        if (needsEmployeeName && !form.employee_name.trim()) {
            showAlert("Укажите сотрудника и дату", "error");
            return;
        }
        if (isInterview && !form.interview_time) {
            showAlert("Укажите время собеседования", "error");
            return;
        }
        if (isInterview && !interviewHrPicked) {
            showAlert("Выберите Telegram сотрудника из ERP-подсказок", "error");
            return;
        }
        if (isPermanent && !form.repeat_interval_unit) {
            showAlert("Укажите, как часто повторять постоянное событие", "error");
            return;
        }
        if (isInterview && !form.candidate_id) {
            showAlert("Выберите кандидата для собеседования", "error");
            return;
        }
        setIsSubmitting(true);
        try {
            await createEvent({
                remind_before: normalizeRemindBefore(form.remind_before),
                remind_at_time: form.remind_at_time?.trim() || null,
                type: form.type,
                event_date: form.event_date,
                employee_name: needsEmployeeName ? form.employee_name.trim() : null,
                child_name: form.type === "child_birthday" ? form.child_name : null,
                telegram_user: form.telegram_user?.trim() || null,
                note: form.note?.trim() || null,
                repeat_interval_count: isPermanent
                    ? Number(form.repeat_interval_count) || 1
                    : null,
                repeat_interval_unit: isPermanent ? form.repeat_interval_unit : null,
            });
            const pendingInvite = isInterview && form.candidate_id
                ? {
                    candidate: {
                        id: Number(form.candidate_id),
                        full_name: form.candidate_name,
                    },
                    date: form.event_date,
                    time: form.interview_time,
                }
                : null;
            setForm({
                type: "birthday",
                employee_name: "",
                vacancy_name: "",
                child_name: "",
                telegram_user: "",
                note: "",
                event_date: "",
                interview_time: "",
                remind_before: 3,
                remind_at_time: "",
                repeat_interval_count: 1,
                repeat_interval_unit: "month",
                candidate_id: "",
                candidate_name: "",
                candidate_search: "",
            });
            setInterviewHrPicked(false);
            nameSearch.clear();
            tgSearch.clear();
            onRefresh?.();
            showAlert("Событие сохранено", "success");
            if (pendingInvite) {
                const wantHh = window.confirm(
                    "Отправить кандидату сообщение о собеседовании на hh.ru?"
                );
                if (wantHh) setInviteState(pendingInvite);
            }
        } catch (err) {
            showAlert(`Ошибка: ${err.message}`, "error");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <>
        <form onSubmit={submit} className="flex-1 flex flex-wrap gap-4 items-end">
            <div className="w-full sm:w-auto flex-1 min-w-[200px]">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Тип события</label>
                <div className="relative">
                    <select 
                        value={form.type} 
                        onChange={(e) => {
                            const type = e.target.value;
                            setForm((prev) => ({
                                ...prev,
                                type,
                                employee_name: eventTypeRequiresEmployeeName(type)
                    ? prev.employee_name
                    : "",
                                vacancy_name: type === "interview" ? prev.vacancy_name : "",
                                child_name: type === "child_birthday" ? prev.child_name : "",
                                interview_time: type === "interview" ? prev.interview_time : "",
                                candidate_id: type === "interview" ? prev.candidate_id : "",
                                candidate_name: type === "interview" ? prev.candidate_name : "",
                                candidate_search: type === "interview" ? prev.candidate_search : "",
                                repeat_interval_unit: type === "permanent"
                                    ? (prev.repeat_interval_unit || "month")
                                    : prev.repeat_interval_unit,
                                repeat_interval_count: type === "permanent"
                                    ? (prev.repeat_interval_count || 1)
                                    : prev.repeat_interval_count,
                            }));
                            if (type !== "interview") setInterviewHrPicked(false);
                            if (!eventTypeRequiresEmployeeName(type)) nameSearch.clear();
                        }}
                        className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                    >
                        {EVENT_TYPE_OPTIONS.map((item) => (
                            <option key={item.value} value={item.value}>
                                {item.label}
                            </option>
                        ))}
                    </select>
                    <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                    </div>
                </div>
            </div>

            {needsEmployeeName && (
            <div className="w-full sm:w-auto flex-1 min-w-[200px] relative">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Сотрудник</label>
                    <input 
                    type="text" 
                    placeholder="Начните вводить ФИО"
                    value={form.employee_name} 
                    onChange={(e) => {
                        setForm({ ...form, employee_name: e.target.value });
                        nameSearch.setShowSuggestions(true);
                    }}
                    onFocus={nameSearch.openIfAny}
                    onBlur={nameSearch.scheduleClose}
                    autoComplete="off"
                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                />
                <SuggestionDropdown
                    visible={nameSearch.showSuggestions && form.employee_name.trim().length >= 2}
                    isSearching={nameSearch.isSearching}
                    suggestions={nameSearch.suggestions}
                    emptyText="Никого не найдено в ERP"
                    onPick={pickNameSuggestion}
                    primaryKey="full_name"
                    secondaryKey="tg_username"
                />
            </div>
            )}

            {isInterview && (
                <div className="w-full sm:w-auto flex-1 min-w-[220px]">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                        Кандидат
                    </label>
                    <input
                        type="text"
                        placeholder="Поиск по ФИО"
                        value={form.candidate_search}
                        onChange={(e) => setForm({ ...form, candidate_search: e.target.value })}
                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all mb-2"
                        data-testid="event-candidate-search"
                    />
                    <select
                        value={form.candidate_id}
                        onChange={(e) => {
                            const id = e.target.value;
                            const picked = candidateOptions.find((c) => String(c.id) === String(id));
                            setForm((prev) => ({
                                ...prev,
                                candidate_id: id,
                                candidate_name: picked?.full_name || prev.candidate_name,
                            }));
                        }}
                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                        data-testid="event-candidate-select"
                    >
                        <option value="">
                            {candidatesLoading ? "Загрузка…" : "-- Выберите кандидата --"}
                        </option>
                        {candidateOptions.map((c) => (
                            <option key={c.id} value={c.id}>
                                {c.full_name || `Кандидат #${c.id}`}
                            </option>
                        ))}
                    </select>
                </div>
            )}

            {isInterview && (
                <div className="w-full sm:w-auto flex-1 min-w-[200px]">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Вакансия</label>
                    <input
                        type="text"
                        placeholder="Название вакансии"
                        value={form.vacancy_name}
                        onChange={(e) => setForm({ ...form, vacancy_name: e.target.value })}
                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                    />
                </div>
            )}

            {form.type === "child_birthday" && (
                <div className="w-full sm:w-auto flex-1 min-w-[200px]">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Ребёнок</label>
                    <input 
                        type="text" 
                        placeholder="Имя ребёнка" 
                        value={form.child_name} 
                        onChange={(e) => setForm({ ...form, child_name: e.target.value })}
                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                    />
                </div>
            )}

            {isInterview && (
                <div className="w-full sm:w-auto min-w-[150px]">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                        Время собеседования
                    </label>
                    <input
                        type="time"
                        value={form.interview_time}
                        onChange={(e) => setForm({ ...form, interview_time: e.target.value })}
                        className="w-full h-[42px] border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                    />
                </div>
            )}

            <div className="w-full sm:w-auto min-w-[150px]">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Дата</label>
                <input 
                    type="date" 
                    value={form.event_date} 
                    onChange={(e) => setForm({ ...form, event_date: e.target.value })}
                    className="w-full h-[42px] border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                />
            </div>

            {isPermanent && (
                <>
                    <div className="w-full sm:w-auto min-w-[110px]">
                        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Каждые</label>
                        <input
                            type="number"
                            min={1}
                            max={365}
                            value={form.repeat_interval_count}
                            onChange={(e) => setForm({ ...form, repeat_interval_count: e.target.value })}
                            className="w-full h-[42px] border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            data-testid="event-repeat-count"
                        />
                    </div>
                    <div className="w-full sm:w-auto min-w-[150px]">
                        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Промежуток</label>
                        <select
                            value={form.repeat_interval_unit}
                            onChange={(e) => setForm({ ...form, repeat_interval_unit: e.target.value })}
                            className="w-full h-[42px] appearance-none border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            data-testid="event-repeat-unit"
                        >
                            {REPEAT_INTERVAL_OPTIONS.map((item) => (
                                <option key={item.value} value={item.value}>
                                    {item.label}
                                </option>
                            ))}
                        </select>
                    </div>
                </>
            )}

            <div className="w-full sm:w-auto min-w-[120px]">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Напомнить за (дней)</label>
                <input 
                    type="number" 
                    placeholder="Дней" 
                    value={form.remind_before} 
                    onChange={(e) => setForm({ ...form, remind_before: e.target.value })}
                    className="w-full h-[42px] border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                />
            </div>

            <div className="w-full sm:w-auto min-w-[150px]">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    Напомнить во сколько
                </label>
                <input
                    type="time"
                    value={form.remind_at_time}
                    onChange={(e) => setForm({ ...form, remind_at_time: e.target.value })}
                    className="w-full h-[42px] border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                />
            </div>

            <div className="w-full sm:w-auto flex-1 min-w-[220px] relative">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Telegram сотрудника</label>
                <input
                    type="text"
                    placeholder={isInterview ? "Выберите сотрудника из ERP" : "@username"}
                    value={form.telegram_user}
                    onChange={(e) => {
                        setForm({ ...form, telegram_user: e.target.value });
                        if (isInterview) setInterviewHrPicked(false);
                        tgSearch.setShowSuggestions(true);
                    }}
                    onFocus={tgSearch.openIfAny}
                    onBlur={tgSearch.scheduleClose}
                    autoComplete="off"
                    className="w-full h-[42px] border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                />
                <SuggestionDropdown
                    visible={
                        tgSearch.showSuggestions
                        && form.telegram_user.trim().replace(/^@+/, "").length >= 2
                    }
                    isSearching={tgSearch.isSearching}
                    suggestions={tgSearch.suggestions}
                    emptyText={isInterview ? "HR пользователь не найден в ERP" : "Telegram не найден в ERP"}
                    onPick={pickTelegramSuggestion}
                    primaryKey={isInterview ? "full_name" : "tg_username"}
                    secondaryKey={isInterview ? "tg_username" : "full_name"}
                />
            </div>

            <div className="w-full">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Дополнительная информация / заметка</label>
                <textarea
                    placeholder="Введите заметку по событию"
                    value={form.note}
                    onChange={(e) => setForm({ ...form, note: e.target.value })}
                    rows={3}
                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all resize-y"
                />
            </div>

            <button 
                type="submit" 
                disabled={isSubmitting}
                className="w-full sm:w-auto bg-slate-900 text-white px-6 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center justify-center gap-2 h-[42px] disabled:opacity-70"
            >
                {isSubmitting ? (
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                )}
                Добавить
            </button>
        </form>
        <InterviewInviteModal
            open={Boolean(inviteState)}
            candidate={inviteState?.candidate}
            defaultDate={inviteState?.date || ""}
            defaultTime={inviteState?.time || ""}
            lockSchedule
            onClose={() => setInviteState(null)}
            onSubmit={async (message, schedule, reminder) => {
                const hrId = user?.erp_user_id || user?.id;
                try {
                    const resp = await sendInterviewInvite(inviteState.candidate.id, {
                        message,
                        hr_id: hrId || null,
                        interview_date: schedule?.date || inviteState.date,
                        start_time: schedule?.startTime || inviteState.time,
                        end_time: schedule?.endTime,
                        book_calendar: Boolean(hrId),
                        remind_candidate: Boolean(reminder?.enabled),
                        remind_at: reminder?.remind_at || null,
                        reminder_message: reminder?.message || null,
                    });
                    if (resp?.delivery && resp.delivery !== "sent" && resp.delivery !== "ok") {
                        showAlert(
                            resp?.warning || "Собеседование сохранено, но HH пока не принял приглашение.",
                            "warning"
                        );
                    } else {
                        showAlert("Приглашение на собеседование отправлено кандидату в HH", "success");
                    }
                    setInviteState(null);
                } catch (err) {
                    showAlert(`Ошибка отправки приглашения: ${err?.message || err}`, "error");
                    throw err;
                }
            }}
        />
        </>
    );
};

export default EventNotificationSetup;
