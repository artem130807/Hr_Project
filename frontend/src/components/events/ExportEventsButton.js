import React from "react";
import * as XLSX from "xlsx";
import { getEventTypeMeta, formatRepeatInterval } from "./eventTypes";
import { formatDateRu } from "../../utils/dateFormat";
import { documentFilename } from "../../utils/documentFilename";

const ExportEventsButton = ({ events }) => {
    const exportToExcel = () => {
        const data = events.map((e) => ({
            Тип: getEventTypeMeta(e.type).label,
            Сотрудник: e.employee_name,
            Ребёнок: e.child_name || "",
            "Telegram сотрудника": e.telegram_user || "",
            Заметка: e.note || "",
            Дата: formatDateRu(e.event_date),
            НапоминатьЗа: e.remind_before,
            НапомнитьВоСколько: e.remind_at_time || "",
            Повтор: formatRepeatInterval(e.repeat_interval_count, e.repeat_interval_unit),
            Статус: e.is_done ? "Завершено" : "Ожидает",
        }));

        const worksheet = XLSX.utils.json_to_sheet(data);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Events");
        XLSX.writeFile(workbook, documentFilename({ type: "События сотрудников", date: new Date(), extension: "xlsx" }));
    };

    return (
        <button 
            onClick={exportToExcel} 
            className="flex items-center gap-2 px-4 py-2.5 h-[42px] bg-white border border-slate-200 text-slate-700 rounded-xl hover:bg-slate-50 transition-colors shadow-sm text-sm font-medium"
        >
            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Экспорт Excel
        </button>
    );
};

export default ExportEventsButton;
