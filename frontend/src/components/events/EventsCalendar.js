import React, { useMemo, useState } from "react";
import dayjs from "dayjs";
import "dayjs/locale/ru";
import { getEventTypeMeta, formatRepeatInterval } from "./eventTypes";

dayjs.locale("ru");

const EventsCalendar = ({ events }) => {
    const [currentDate, setCurrentDate] = useState(dayjs());
    
    // Create calendar grid for the current month
    const calendarDays = useMemo(() => {
        const startOfMonth = currentDate.startOf("month");
        const endOfMonth = currentDate.endOf("month");
        
        // Find the first day of the week (Monday)
        const firstDayOfWeek = startOfMonth.day() === 0 ? 6 : startOfMonth.day() - 1; // 0 is Sunday in JS, we want Monday as 0
        const startDate = startOfMonth.subtract(firstDayOfWeek, "day");
        
        // Find the last day of the week (Sunday)
        const lastDayOfWeek = endOfMonth.day() === 0 ? 0 : 7 - endOfMonth.day();
        const endDate = endOfMonth.add(lastDayOfWeek, "day");
        
        const days = [];
        let curr = startDate;
        
        while (curr.isBefore(endDate) || curr.isSame(endDate, "day")) {
            days.push(curr);
            curr = curr.add(1, "day");
        }
        
        return days;
    }, [currentDate]);

    const pendingEvents = events.filter(e => !e.is_done);
    
    // Group events by YYYY-MM-DD
    const eventsByDate = useMemo(() => {
        const grouped = {};
        pendingEvents.forEach(ev => {
            const dateKey = dayjs(ev.event_date).format("YYYY-MM-DD");
            if (!grouped[dateKey]) grouped[dateKey] = [];
            grouped[dateKey].push(ev);
        });
        return grouped;
    }, [pendingEvents]);

    const handlePrevMonth = () => setCurrentDate(prev => prev.subtract(1, "month"));
    const handleNextMonth = () => setCurrentDate(prev => prev.add(1, "month"));
    const handleToday = () => setCurrentDate(dayjs());

    if (pendingEvents.length === 0 && events.length > 0) {
        return (
            <div className="text-center py-10 bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200">
                <p className="text-slate-500 font-medium">Все события выполнены</p>
            </div>
        );
    }

    if (events.length === 0) {
        return (
            <div className="text-center py-10 bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200">
                <p className="text-slate-500 font-medium">Нет событий для отображения</p>
            </div>
        );
    }

    const weekDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

    return (
        <div className="flex flex-col h-full bg-white">
            {/* Calendar Header */}
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-black text-slate-800 capitalize tracking-tight">
                    {currentDate.format("MMMM YYYY")}
                </h2>
                <div className="flex items-center gap-2 bg-slate-100/50 p-1 rounded-xl">
                    <button 
                        onClick={handlePrevMonth}
                        className="p-2 text-slate-500 hover:text-slate-700 hover:bg-white rounded-lg transition-colors shadow-sm"
                        title="Предыдущий месяц"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                    </button>
                    <button 
                        onClick={handleToday}
                        className="px-4 py-2 text-sm font-semibold text-slate-700 hover:text-slate-900 hover:bg-white rounded-lg transition-colors shadow-sm"
                    >
                        Сегодня
                    </button>
                    <button 
                        onClick={handleNextMonth}
                        className="p-2 text-slate-500 hover:text-slate-700 hover:bg-white rounded-lg transition-colors shadow-sm"
                        title="Следующий месяц"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Calendar Grid */}
            <div className="border border-slate-200/60 rounded-2xl overflow-hidden bg-slate-50/50">
                {/* Day Names */}
                <div className="grid grid-cols-7 border-b border-slate-200/60 bg-slate-100/50">
                    {weekDays.map((day, idx) => (
                        <div key={day} className={`py-3 text-center text-xs font-bold uppercase tracking-wider ${idx >= 5 ? 'text-red-400' : 'text-slate-500'}`}>
                            {day}
                        </div>
                    ))}
                </div>
                
                {/* Days */}
                <div className="grid grid-cols-7 auto-rows-[minmax(120px,auto)]">
                    {calendarDays.map((day, idx) => {
                        const isCurrentMonth = day.isSame(currentDate, "month");
                        const isToday = day.isSame(dayjs(), "day");
                        const isWeekend = day.day() === 0 || day.day() === 6;
                        const dateString = day.format("YYYY-MM-DD");
                        const dayEvents = eventsByDate[dateString] || [];
                        
                        return (
                            <div 
                                key={dateString}
                                className={`
                                    min-h-[120px] p-2 border-r border-b border-slate-200/40 relative group transition-colors
                                    ${!isCurrentMonth ? "bg-slate-100/50 opacity-60" : "bg-white"}
                                    ${idx % 7 === 6 ? "border-r-0" : ""}
                                    hover:bg-blue-50/30
                                `}
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <span className={`
                                        flex items-center justify-center w-7 h-7 rounded-full text-sm font-semibold
                                        ${isToday ? "bg-blue-600 text-white shadow-md" : 
                                          isWeekend ? "text-red-500" : "text-slate-700"}
                                    `}>
                                        {day.format("D")}
                                    </span>
                                    
                                    {dayEvents.length > 0 && (
                                        <span className="text-[10px] font-bold bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">
                                            {dayEvents.length}
                                        </span>
                                    )}
                                </div>
                                
                                <div className="space-y-1.5 overflow-y-auto max-h-[85px] no-scrollbar">
                                    {dayEvents.sort((a,b) => new Date(a.event_date) - new Date(b.event_date)).map(e => {
                                        const meta = getEventTypeMeta(e.type);
                                        return (
                                            <div 
                                                key={e.id}
                                                className="group/event relative text-xs p-1.5 rounded-lg border border-transparent hover:border-slate-200 shadow-sm cursor-default transition-all bg-white"
                                            >
                                                <div className={`absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full ${meta.stripeClass}`}></div>
                                                <div className="pl-2.5 flex items-start gap-1">
                                                    <span className="text-[11px] leading-tight flex-1 font-medium text-slate-700 truncate" title={e.employee_name || meta.label}>
                                                        {meta.icon} {e.employee_name || meta.label}
                                                    </span>
                                                </div>
                                                
                                                {/* Tooltip on hover */}
                                                <div className="absolute hidden group-hover/event:block z-50 w-48 p-3 bg-slate-800 text-white rounded-xl shadow-xl -top-2 left-full ml-2 text-xs">
                                                    <div className="font-bold mb-1 border-b border-slate-600 pb-1">{meta.label}</div>
                                                    <div className="font-medium">{e.employee_name || meta.label}</div>
                                                    {e.child_name && <div className="text-slate-300 mt-1">Ребёнок: {e.child_name}</div>}
                                                    {e.telegram_user && <div className="text-slate-300 mt-1 truncate">TG: {e.telegram_user}</div>}
                                                    {e.repeat_interval_unit && (
                                                        <div className="text-violet-300 mt-1">
                                                            {formatRepeatInterval(e.repeat_interval_count, e.repeat_interval_unit)}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
            
            <style jsx>{`
                .no-scrollbar::-webkit-scrollbar {
                    display: none;
                }
                .no-scrollbar {
                    -ms-overflow-style: none;
                    scrollbar-width: none;
                }
            `}</style>
        </div>
    );
};

export default EventsCalendar;