import React from "react";
import dayjs from "dayjs";
import { updateEvent } from "../../services/eventsApi";
import { useAlertContext } from "../../context/AlertContext";
import { getEventTypeMeta, formatRepeatInterval } from "./eventTypes";
import { formatDateRu } from "../../utils/dateFormat";

const EventList = ({ events, onRefresh }) => {
    const { showAlert } = useAlertContext();

    const markDone = async (id) => {
        try {
            await updateEvent(id, { is_done: true });
            onRefresh();
            showAlert("Событие завершено", "success");
        } catch (e) {
            showAlert(`Ошибка: ${e.message}`, "error");
        }
    };

    const moveDate = async (id, currentDate) => {
        const hint = currentDate ? formatDateRu(currentDate, "") : "";
        const raw = prompt("Новая дата (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД):", hint);
        if (!raw) return;
        let newDate = raw.trim();
        const dmy = newDate.match(/^(\d{1,2})[./](\d{1,2})[./](\d{4})$/);
        if (dmy) {
            newDate = `${dmy[3]}-${dmy[2].padStart(2, "0")}-${dmy[1].padStart(2, "0")}`;
        }
        if (!/^\d{4}-\d{2}-\d{2}$/.test(newDate)) {
            showAlert("Дата должна быть в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД", "error");
            return;
        }
        try {
            await updateEvent(id, { event_date: newDate });
            onRefresh();
            showAlert("Дата изменена", "success");
        } catch (e) {
            showAlert(`Ошибка: ${e.message}`, "error");
        }
    };

    const pendingEvents = events.filter(e => !e.is_done).sort((a, b) => new Date(a.event_date) - new Date(b.event_date));
    const completedEvents = events.filter(e => e.is_done).sort((a, b) => new Date(b.event_date) - new Date(a.event_date));

    const renderEventCard = (e) => {
        const typeMeta = getEventTypeMeta(e.type);

        return (
            <div key={e.id} className={`flex flex-col sm:flex-row justify-between sm:items-center p-4 rounded-xl border ${e.is_done ? 'bg-slate-50 border-slate-200' : 'bg-white border-slate-200 hover:border-[#4f46e5] hover:shadow-sm'} transition-all gap-4`}>
                <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center text-xl ${e.is_done ? 'bg-slate-100 opacity-50' : 'bg-[#4f46e5]/10'}`}>
                        {typeMeta.icon}
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h4 className={`font-bold ${e.is_done ? 'text-slate-500 line-through' : 'text-slate-900'}`}>
                                {e.employee_name || typeMeta.label}
                            </h4>
                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                                {typeMeta.label}
                            </span>
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
                            <span className="flex items-center gap-1">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                                {dayjs(e.event_date).format("DD MMMM YYYY")}
                                {e.remind_before != null && (
                                    <span className="text-slate-400"> · за {e.remind_before} дн.</span>
                                )}
                                {e.remind_at_time && (
                                    <span className="text-slate-400"> · в {String(e.remind_at_time).slice(0, 5)}</span>
                                )}
                                {e.repeat_interval_unit && (
                                    <span className="text-violet-500">
                                        {" "}· {formatRepeatInterval(e.repeat_interval_count, e.repeat_interval_unit)}
                                    </span>
                                )}
                            </span>
                            {e.child_name && (
                                <span className="flex items-center gap-1">
                                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                                    Ребёнок: {e.child_name}
                                </span>
                            )}
                            {e.telegram_user && (
                                <span className="flex items-center gap-1">
                                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12l-18 9 4-9-4-9 18 9z" /></svg>
                                    Телеграм сотрудника: {e.telegram_user}
                                </span>
                            )}
                        </div>
                        {e.note && <p className="mt-2 text-sm text-slate-600">{e.note}</p>}
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                    {!e.is_done && (
                        <>
                            <button
                                className="px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                                onClick={() => moveDate(e.id, e.event_date)}
                            >
                                Перенести
                            </button>
                            <button
                                className="px-3 py-1.5 text-xs font-medium text-[#4f46e5] bg-[#4f46e5]/10 hover:bg-[#4f46e5]/20 rounded-lg transition-colors flex items-center gap-1"
                                onClick={() => markDone(e.id)}
                            >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                Завершить
                            </button>
                        </>
                    )}
                </div>
            </div>
        );
    };

    if (events.length === 0) {
        return (
            <div className="text-center py-10">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-50 mb-4">
                    <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                </div>
                <p className="text-slate-500 font-medium">Нет запланированных событий</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {pendingEvents.length > 0 && (
                <div className="space-y-3">
                    {pendingEvents.map(renderEventCard)}
                </div>
            )}
            
            {completedEvents.length > 0 && (
                <div>
                    <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 border-t border-slate-100 pt-6">Завершенные события</h4>
                    <div className="space-y-3">
                        {completedEvents.map(renderEventCard)}
                    </div>
                </div>
            )}
        </div>
    );
};

export default EventList;
