import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import MainLayout from "../layout/MainLayout";
import { getDashboard } from "../services/analyticsApi";
import { useAlertContext } from "../context/AlertContext";
import { formatDateRu, replaceIsoDatesInText } from "../utils/dateFormat";

const GROUP_LABEL = {
    vacancies: "Вакансии",
    candidates: "Кандидаты",
    calendar: "Календарь",
    other: "Система",
};

const PRIORITY_BORDER = {
    high: "border-red-500",
    medium: "border-indigo-500",
    low: "border-blue-400",
};

const CALENDAR_TYPE_LABEL = {
    birthday: "День рождения",
    child_birthday: "День рождения ребенка",
    work_anniversary: "Годовщина работы",
    interview: "Собеседование",
    permanent: "Постоянное",
    other: "Другое событие",
};

function normalizeDashboardTask(task) {
    if (!task || typeof task !== "object") return task;
    const out = { ...task };
    out.description = replaceIsoDatesInText(out.description);
    out.meta = replaceIsoDatesInText(out.meta);

    const title = String(out.title || "");
    const m = title.match(/^([a-z_]+):\s*(.+)$/i);
    if (m) {
        const key = m[1].toLowerCase();
        const entity = m[2];
        const label = CALENDAR_TYPE_LABEL[key];
        if (label) out.title = `${label}: ${entity}`;
    }

    if (out.meta && /^\d{4}-\d{2}-\d{2}$/.test(String(out.meta))) {
        out.meta = formatDateRu(out.meta);
    }
    return out;
}

export default function Dashboard() {
    const { user } = useAuth();
    const { showAlert } = useAlertContext();
    const [data, setData] = useState({ summary: {}, tasks: [] });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                setLoading(true);
                const res = await getDashboard();
                if (!cancelled) setData(res || { summary: {}, tasks: [] });
            } catch (e) {
                console.error(e);
                if (!cancelled) {
                    showAlert(`Не удалось загрузить задачи: ${e.message || e}`, "error");
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const summary = data.summary || {};
    const tasks = Array.isArray(data.tasks) ? data.tasks.map(normalizeDashboardTask) : [];
    const byGroup = tasks.reduce((acc, t) => {
        const g = t.group || "other";
        if (!acc[g]) acc[g] = [];
        acc[g].push(t);
        return acc;
    }, {});

    return (
        <MainLayout>
            <div className="mb-8">
                <h1 className="text-3xl font-bold tracking-tight text-slate-900">
                    С возвращением, {user?.name}!
                </h1>
                <p className="mt-2 text-slate-500">Вот что происходит сегодня в вашей компании.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {[
                    ["Активных вакансий", summary.active_vacancies, "bg-blue-50 text-blue-600"],
                    ["Кандидатов в работе", summary.candidates_in_work, "bg-green-50 text-green-600"],
                    ["Ожидают решения", summary.pending_offers, "bg-yellow-50 text-yellow-600"],
                    ["Просроченных задач", summary.overdue_tasks, "bg-red-50 text-red-600"],
                ].map(([label, value, colorClass]) => (
                    <div key={label} className="bg-white rounded-2xl shadow-sm border border-slate-200/60 p-6 flex flex-col justify-between transition-transform hover:-translate-y-1 duration-300">
                        <div className="flex items-center justify-between mb-4">
                            <div className="text-sm font-medium text-slate-500 leading-tight">{label}</div>
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${colorClass}`}>
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                            </div>
                        </div>
                        <div className="text-3xl font-bold text-slate-900">{value ?? 0}</div>
                    </div>
                ))}
            </div>

            <div className="mb-8 flex flex-wrap gap-3">
                <Link to="/requests" className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 transition-colors rounded-xl text-white text-sm font-medium shadow-sm">
                    Создать / открыть заявки
                </Link>
                <Link to="/candidates" className="px-5 py-2.5 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors rounded-xl text-slate-700 text-sm font-medium shadow-sm">
                    Кандидаты
                </Link>
                <Link to="/vacancies" className="px-5 py-2.5 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors rounded-xl text-slate-700 text-sm font-medium shadow-sm">
                    Вакансии
                </Link>
                <Link to="/calendar" className="px-5 py-2.5 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors rounded-xl text-slate-700 text-sm font-medium shadow-sm">
                    Календарь
                </Link>
            </div>

            {loading ? (
                <div className="flex justify-center items-center py-20 text-slate-400">
                    <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Загрузка задач...
                </div>
            ) : tasks.length === 0 ? (
                <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    </div>
                    <h3 className="text-lg font-medium text-slate-800">Всё под контролем!</h3>
                    <p className="text-slate-500 mt-1">Нет срочных задач или уведомлений.</p>
                </div>
            ) : (
                <div className="grid lg:grid-cols-2 gap-6">
                    {Object.entries(byGroup).map(([group, items]) => (
                        <section key={group} className="bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-hidden flex flex-col">
                            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                                <h2 className="font-semibold text-slate-800 flex items-center gap-2">
                                    {GROUP_LABEL[group] || group}
                                </h2>
                                <span className="text-xs font-medium bg-white text-slate-600 border border-slate-200 px-2.5 py-1 rounded-full shadow-sm">
                                    {items.length}
                                </span>
                            </div>
                            <div className="p-6 flex-1 bg-white">
                                <ul className="space-y-4">
                                    {items.map((task) => (
                                        <li
                                            key={task.id}
                                            className={`relative pl-4 py-1`}
                                        >
                                            <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-full ${PRIORITY_BORDER[task.priority] || "bg-slate-300"}`} />
                                            <div className="flex justify-between items-start gap-4">
                                                <div>
                                                    <div className="font-semibold text-slate-900 leading-snug mb-1">{task.title}</div>
                                                    <div className="text-sm text-slate-600 mb-2 leading-relaxed">{task.description}</div>
                                                    {task.meta && <span className="inline-block px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs font-medium mb-2">{task.meta}</span>}
                                                </div>
                                            </div>
                                            <Link to={task.href} className="text-sm font-medium text-[#4f46e5] hover:text-[#b8952b] transition-colors flex items-center gap-1">
                                                Перейти
                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </section>
                    ))}
                </div>
            )}
        </MainLayout>
    );
}