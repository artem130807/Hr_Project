import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import MainLayout from "../layout/MainLayout";
import { useAlertContext } from "../context/AlertContext";
import { useAuth } from "../context/AuthContext";
import { getUsers } from "../services/userApi";
import { getHiredEmployees } from "../services/hrOpsApi";
import { filterCheckpoints } from "../adaptation/filters";
import { formatDateRu, initials, KIND_LABELS, RISK_LABELS, STATUS_LABELS } from "../adaptation/rules";
import AdaptationTakeLinks from "../adaptation/AdaptationTakeLinks";
import { adaptationFormAbsoluteUrl, copyText } from "../adaptation/takeLinks";
import {
    enrollAdaptation,
    createTemporaryAdaptation,
    getAdaptationReports,
    getAdaptationNotificationErrors,
    getAdaptationNotificationTemplates,
    getAdaptationSettings,
    getAdaptationTakeLinks,
    listAdaptationCheckpoints,
    updateAdaptationSettings,
    updateAdaptationNotificationTemplate,
    retryAdaptationNotification,
} from "../services/adaptationApi";

const STATUS_BADGE = {
    planned: "bg-slate-100 text-slate-600",
    collecting: "bg-amber-50 text-amber-800",
    overdue: "bg-red-50 text-red-700",
    data_collected: "bg-sky-50 text-sky-800",
    draft_ready: "bg-violet-50 text-violet-800",
    completed: "bg-emerald-50 text-emerald-800",
    forced_completed: "bg-orange-50 text-orange-800",
};

const DOT_CLASS = {
    waiting: "border-slate-300 text-slate-400 bg-white",
    done: "border-emerald-500 text-emerald-700 bg-emerald-50",
    muted: "border-slate-200 text-slate-300 bg-slate-50",
};

const RISK_CLASS = {
    high: "text-red-700",
    critical: "text-red-900 font-semibold",
    medium: "text-amber-700",
    low: "text-emerald-700",
    uncalculated: "text-slate-500",
};
const OPTIONAL_COLUMNS = [
    ["position", "Должность"], ["progress", "Ответы"], ["risk", "Итог и риск"],
];

const NOTIFICATION_AUDIENCE_LABELS = {
    employee: "Сотруднику",
    manager: "Руководителю",
    hr: "HR-специалистам",
};

const NOTIFICATION_EVENT_LABELS = {
    initial: "Первое уведомление",
    reminder: "Напоминание в день заполнения",
    next_day: "Напоминание о просрочке",
    missing_16: "Не все формы заполнены",
    overdue_12: "Форма не заполнена на следующий день",
    data_collected: "Ответы собраны",
};

const NOTIFICATION_EVENT_HINTS = {
    initial: "Отправляется утром в день планового этапа.",
    reminder: "Отправляется повторно, если форма ещё не заполнена.",
    next_day: "Отправляется сотруднику после наступления просрочки.",
    missing_16: "Сообщает HR, что к концу дня не хватает ответов.",
    overdue_12: "Сообщает HR о незаполненной форме на следующий день.",
    data_collected: "Сообщает HR, что можно подготовить заключение.",
};

const TEMPLATE_VARIABLES = [
    ["{full_name}", "ФИО сотрудника"],
    ["{stage}", "Название этапа"],
    ["{plan_date}", "Плановая дата"],
    ["{link}", "Персональная ссылка"],
];

function notificationPreview(text = "") {
    return text
        .replaceAll("{full_name}", "Иванов Иван Иванович")
        .replaceAll("{stage}", "Первый месяц")
        .replaceAll("{plan_date}", "15.09.2026")
        .replaceAll("{link}", "https://hr.example.ru/adaptation/forms/…");
}

function monthOptions(now = new Date()) {
    const out = [];
    const start = new Date(now.getFullYear(), now.getMonth() - 6, 1);
    for (let i = 0; i < 18; i += 1) {
        const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
        out.push({
            year: d.getFullYear(),
            month: d.getMonth() + 1,
            label: d.toLocaleDateString("ru-RU", { month: "long", year: "numeric" }),
        });
    }
    return out;
}

export default function AdaptationPage() {
    const { showAlert } = useAlertContext();
    const { user } = useAuth() || {};
    const isHr = ["superadmin", "admin", "manager", "senior_manager", "hr", "owner", "dev", "tech_admin", "director"].includes(user?.role);
    const navigate = useNavigate();
    const today = new Date();
    const [year, setYear] = useState(today.getFullYear());
    const [month, setMonth] = useState(today.getMonth() + 1);
    const [q, setQ] = useState("");
    const [department, setDepartment] = useState("");
    const [kind, setKind] = useState("");
    const [risk, setRisk] = useState("");
    const [route, setRoute] = useState("");
    const [outcome, setOutcome] = useState("");
    const [status, setStatus] = useState("");
    const [dateScope, setDateScope] = useState("");
    const [hideCompleted, setHideCompleted] = useState(false);
    const [showArchived, setShowArchived] = useState(false);
    const [payload, setPayload] = useState({
        period_label: "Этапы",
        year: today.getFullYear(),
        month: today.getMonth() + 1,
        attention: { overdue: 0, this_week: 0, ready_hr: 0 },
        items: [],
    });
    const [loading, setLoading] = useState(false);
    const [showEnroll, setShowEnroll] = useState(false);
    const [showReport, setShowReport] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [includeControl, setIncludeControl] = useState(false);
    const [enrollRoute, setEnrollRoute] = useState("full");
    const [erpStaff, setErpStaff] = useState([]);
    const [hiredStaff, setHiredStaff] = useState([]);
    const [enrollId, setEnrollId] = useState("");
    const [enrollQuery, setEnrollQuery] = useState("");
    const [enrollLoading, setEnrollLoading] = useState(false);
    const [report, setReport] = useState(null);
    const [temporaryMode, setTemporaryMode] = useState(false);
    const [temporary, setTemporary] = useState({ full_name: "", position: "", department: "", start_date: "", manager_user_id: "", manager_name: "" });
    const [settings, setSettings] = useState({ overdue_enabled: true, overdue_time: "09:00", timezone: "Europe/Samara", show_photo: true, allow_personal_telegram_fallback: false, fallback_role: "hr", manual_share_confirmation_hours: 24 });
    const [notificationTemplates, setNotificationTemplates] = useState([]);
    const [notificationErrors, setNotificationErrors] = useState([]);
    const [editingTemplate, setEditingTemplate] = useState("");
    const [createdTake, setCreatedTake] = useState(null);

    const load = useCallback(async () => {
        try {
            setLoading(true);
            const data = await listAdaptationCheckpoints({
                year,
                month,
                archived: showArchived,
            });
            if (!data || !Array.isArray(data.items)) {
                throw new Error("empty adaptation payload");
            }
            setPayload(data);
        } catch (err) {
            showAlert(`Не удалось загрузить адаптацию: ${err.message || err}`, "error");
            setPayload({
                period_label: "Этапы",
                year,
                month,
                attention: { overdue: 0, this_week: 0, ready_hr: 0 },
                items: [],
            });
        } finally {
            setLoading(false);
        }
        // showAlert is stable in production; omitting it avoids re-fetch loops in tests.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [year, month, showArchived]);

    useEffect(() => {
        load();
    }, [load]);

    const loadErpStaff = useCallback(async () => {
        try {
            const [rows, hired] = await Promise.all([
                getUsers().catch((err) => {
                    showAlert(`Не удалось загрузить сотрудников ERP: ${err.message || err}`, "error");
                    return [];
                }),
                getHiredEmployees().catch(() => []),
            ]);
            const erpRows = Array.isArray(rows) ? rows : [];
            const hiredRows = Array.isArray(hired) ? hired : [];
            setErpStaff(erpRows);
            setHiredStaff(hiredRows.filter((e) => !e.date_fired));
            return erpRows;
        } catch (err) {
            setErpStaff([]);
            setHiredStaff([]);
            showAlert(`Не удалось загрузить сотрудников: ${err.message || err}`, "error");
            return [];
        }
        // showAlert omitted to avoid re-fetch loops in tests.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        loadErpStaff();
    }, [loadErpStaff]);

    const filtered = useMemo(
        () => filterCheckpoints(payload?.items || [], { q, department, kind, risk, route, outcome, status, hideCompleted, dateScope }),
        [payload.items, q, department, kind, risk, route, outcome, status, hideCompleted, dateScope]
    );

    const attention = payload.attention || { overdue: 0, this_week: 0, ready_hr: 0 };
    const departments = useMemo(() => {
        const fromErp = erpStaff.map((u) => u.department).filter(Boolean);
        const fromHired = hiredStaff.map((u) => u.department).filter(Boolean);
        const fromRows = (payload.items || []).map((r) => r.department).filter(Boolean);
        return Array.from(new Set([...fromErp, ...fromHired, ...fromRows])).sort();
    }, [erpStaff, hiredStaff, payload.items]);

    const enrollCandidates = useMemo(() => {
        const needle = enrollQuery.trim().toLowerCase();
        const hiredMapped = hiredStaff.map((e) => ({
            local_id: e.id,
            id: e.erp_user_id || `emp-${e.id}`,
            erp_user_id: e.erp_user_id || "",
            full_name: e.full_name,
            username: e.erp_user_id || "",
            department: e.department,
            position: e.position,
            role: "",
        }));
        const byKey = new Map();
        [...hiredMapped, ...erpStaff.filter((u) => u.id || u.erp_user_id)].forEach((u) => {
            const key = String(u.erp_user_id || u.local_id || u.id);
            if (!byKey.has(key)) byKey.set(key, u);
        });
        const rows = Array.from(byKey.values());
        if (!needle) return rows;
        return rows.filter((u) => {
            const hay = `${u.full_name || ""} ${u.username || ""} ${u.department || ""} ${u.position || ""} ${u.role || ""}`.toLowerCase();
            return hay.includes(needle);
        });
    }, [erpStaff, hiredStaff, enrollQuery]);

    const openEnroll = async () => {
        setShowEnroll(true);
        setEnrollId("");
        setEnrollQuery("");
        setEnrollRoute("full");
        setTemporaryMode(false);
        setCreatedTake(null);
        await loadErpStaff();
    };

    const submitEnroll = async (e) => {
        e.preventDefault();
        if (!temporaryMode && !enrollId) return;
        try {
            setEnrollLoading(true);
            if (temporaryMode) {
                const created = await createTemporaryAdaptation({ ...temporary, route: enrollRoute });
                let links = created.take_links || [];
                if (!links.length && created.id) {
                    const fetched = await getAdaptationTakeLinks(created.id).catch(() => null);
                    links = fetched?.links || [];
                }
                setCreatedTake({
                    enrollment_id: created.id,
                    employee_id: created.employee_id || null,
                    full_name: temporary.full_name,
                    links,
                });
                showAlert("Временная карточка и план адаптации созданы. Скопируйте ссылку сотруднику.", "success");
                load();
                return;
            }
            const selected = enrollCandidates.find((h) => String(h.erp_user_id || h.id) === String(enrollId));
            const payload = {
                route: enrollRoute,
                include_control_2m: enrollRoute === "control" ? true : includeControl,
            };
            if (selected?.local_id) {
                payload.employee_id = selected.local_id;
                if (selected.erp_user_id) payload.erp_user_id = String(selected.erp_user_id);
            } else {
                payload.erp_user_id = String(selected?.erp_user_id || enrollId);
            }
            const created = await enrollAdaptation(payload);
            const take = {
                enrollment_id: created.id,
                employee_id: created.employee_id,
                full_name: selected?.full_name || created.full_name,
                links: created.take_links || [],
            };
            if (!take.links.length && created.id) {
                const fetched = await getAdaptationTakeLinks(created.id).catch(() => null);
                take.links = fetched?.links || [];
                take.employee_id = take.employee_id || fetched?.employee_id;
                take.full_name = take.full_name || fetched?.full_name;
            }
            setCreatedTake(take);
            showAlert("Сотрудник поставлен на адаптацию. Скопируйте ссылку и отправьте её сотруднику.", "success");
            load();
        } catch (err) {
            showAlert(err.message || String(err), "error");
        } finally {
            setEnrollLoading(false);
        }
    };

    const openSettings = async () => {
        setShowSettings(true);
        setEditingTemplate("");
        try {
            const [nextSettings, templates, errors] = await Promise.all([
                getAdaptationSettings(), getAdaptationNotificationTemplates(), getAdaptationNotificationErrors(),
            ]);
            setSettings(nextSettings);
            setNotificationTemplates(templates || []);
            setNotificationErrors(errors || []);
        } catch (error) { showAlert(error.message, "error"); }
    };

    const columnVisible = (name) => !settings.visible_columns?.length || settings.visible_columns.includes(name);
    const toggleColumn = (name) => {
        const current = settings.visible_columns?.length ? settings.visible_columns : OPTIONAL_COLUMNS.map(([key]) => key);
        setSettings({ ...settings, visible_columns: current.includes(name) ? current.filter((key) => key !== name) : [...current, name] });
    };

    const saveSettings = async () => {
        try {
            setSettings(await updateAdaptationSettings(settings));
            await Promise.all(notificationTemplates.map((item) => updateAdaptationNotificationTemplate(item.audience, item.event, { text: item.text, enabled: item.enabled })));
            setShowSettings(false);
            showAlert("Настройки адаптации сохранены", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const retryNotification = async (id) => {
        try {
            await retryAdaptationNotification(id);
            setNotificationErrors((current) => current.filter((item) => item.id !== id));
            showAlert("Уведомление поставлено на повторную отправку", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const openReport = async () => {
        try {
            const data = await getAdaptationReports({ year, month });
            setReport(data);
          } catch (error) {
              showAlert(error.message || "Не удалось сформировать отчет", "error");
              return;
        }
        setShowReport(true);
    };

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <p className="text-xs font-semibold tracking-[0.16em] text-slate-400">ТЕСТЫ / АДАПТАЦИЯ</p>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Адаптация сотрудников</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        Контроль этапов, ответов, рисков и документов по испытательному сроку.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    {isHr ? <button
                        type="button"
                        className="text-sm px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 font-medium"
                        onClick={openSettings}
                    >
                        Настройки
                    </button> : null}
                    {isHr ? <button
                        type="button"
                        className="text-sm px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 font-medium"
                        onClick={openReport}
                        data-testid="adaptation-report"
                    >
                        Сформировать отчет
                    </button> : null}
                    {isHr ? <button
                        type="button"
                        className="bg-slate-900 text-white px-4 py-2.5 rounded-xl hover:bg-slate-800 text-sm font-medium"
                        onClick={openEnroll}
                        data-testid="adaptation-add"
                    >
                        + Добавить сотрудника
                    </button> : null}
                </div>
            </div>

            <section
                className="mb-4 grid gap-3 md:grid-cols-4 bg-white border border-slate-200/60 rounded-2xl p-4 shadow-sm"
                data-testid="adaptation-attention"
            >
                <div className="flex items-center gap-3">
                    <span className="text-2xl font-bold text-red-600">{attention.overdue}</span>
                    <span>
                        <b className="block text-sm">Просрочен</b>
                        <small className="text-slate-500">нет ответа сотрудника</small>
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-2xl font-bold text-[#4f46e5]">{attention.this_week}</span>
                    <span>
                        <b className="block text-sm">На этой неделе</b>
                        <small className="text-slate-500">требуют внимания</small>
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-2xl font-bold text-sky-600">{attention.ready_hr}</span>
                    <span>
                        <b className="block text-sm">Данные собраны</b>
                        <small className="text-slate-500">можно заполнять HR</small>
                    </span>
                </div>
                <p className="text-xs text-slate-500 md:text-right self-center">
                    Просрочка включается только с 09:00 следующего дня при отсутствии ответа сотрудника.
                </p>
            </section>

            <section className="mb-4 bg-white rounded-2xl border border-slate-200/60 shadow-sm p-4 grid gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="adaptation-filters">
                <label className="block text-sm md:col-span-1">
                    <span className="text-slate-500">Период</span>
                    <select
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white"
                        value={`${year}-${month}`}
                        onChange={(e) => {
                            const [y, m] = e.target.value.split("-").map(Number);
                            setYear(y);
                            setMonth(m);
                        }}
                        data-testid="filter-period"
                    >
                        {monthOptions().map((opt) => (
                            <option key={`${opt.year}-${opt.month}`} value={`${opt.year}-${opt.month}`}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                </label>
                <label className="block text-sm md:col-span-1">
                    <span className="text-slate-500">Поиск</span>
                    <input
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2"
                        placeholder="ФИО или должность"
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        data-testid="filter-search"
                    />
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Отдел</span>
                    <select className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white" value={department} onChange={(e) => setDepartment(e.target.value)} data-testid="filter-department">
                        <option value="">Все отделы</option>
                        {departments.map((d) => (
                            <option key={d} value={d}>{d}</option>
                        ))}
                    </select>
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Этап</span>
                    <select className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white" value={kind} onChange={(e) => setKind(e.target.value)}>
                        <option value="">Все этапы</option>
                        {Object.entries(KIND_LABELS).map(([k, label]) => (
                            <option key={k} value={k}>{label}</option>
                        ))}
                    </select>
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Риск</span>
                    <select className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white" value={risk} onChange={(e) => setRisk(e.target.value)}>
                        <option value="">Все риски</option>
                        {Object.entries(RISK_LABELS).map(([k, label]) => (
                            <option key={k} value={k}>{label}</option>
                        ))}
                    </select>
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Статус</span>
                    <select className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white" value={status} onChange={(e) => setStatus(e.target.value)}>
                        <option value="">Все статусы</option>
                        {Object.entries(STATUS_LABELS).map(([k, label]) => (
                            <option key={k} value={k}>{label}</option>
                        ))}
                    </select>
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Маршрут</span>
                    <select className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white" value={route} onChange={(e) => setRoute(e.target.value)}>
                        <option value="">Все</option>
                        <option value="full">Полный</option>
                        <option value="control">Контрольный</option>
                    </select>
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Итог</span>
                    <select className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                        <option value="">Все</option>
                        <option value="Стабильно">Стабильно</option>
                        <option value="Требует внимания">Требует внимания</option>
                        <option value="Критическая ситуация">Критическая ситуация</option>
                    </select>
                </label>
                <label className="flex items-center gap-2 text-sm md:col-span-3 xl:col-span-6">
                    <input type="checkbox" checked={hideCompleted} onChange={(e) => setHideCompleted(e.target.checked)} data-testid="hide-completed" />
                    <span>Скрыть завершенные</span>
                </label>
                <label className="flex items-center gap-2 text-sm md:col-span-3 xl:col-span-6">
                    <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} data-testid="show-archived" />
                    <span>Показать архив адаптаций</span>
                </label>
                <div className="flex flex-wrap items-center gap-2 text-sm md:col-span-3 xl:col-span-6" data-testid="filter-date-scope">
                    <span className="text-slate-500">По дате:</span>
                    {[
                        ["", "Все"],
                        ["overdue", "Просрочено"],
                        ["today", "Сегодня"],
                        ["two_weeks", "Ближайшие 2 недели"],
                        ["later", "Позже"],
                    ].map(([value, label]) => (
                        <button
                            key={value || "all"}
                            type="button"
                            className={`rounded-lg border px-3 py-1.5 ${dateScope === value ? "border-slate-700 bg-slate-800 text-white" : "border-slate-200 bg-white text-slate-600"}`}
                            onClick={() => setDateScope(value)}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </section>

            <section className="bg-white rounded-2xl border border-slate-200/60 shadow-sm overflow-hidden">
                <div className="px-4 py-3 flex items-center justify-between border-b border-slate-100">
                    <div>
                        <b>{showArchived ? "Архив адаптаций" : (payload.period_label || "Этапы")}</b>
                        <span className="ml-2 text-sm text-slate-500">{filtered.length} записей</span>
                    </div>
                    <button type="button" className="text-sm text-slate-600 hover:text-slate-900" onClick={load} disabled={loading}>
                        {loading ? "Обновление…" : "Обновить"}
                    </button>
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full text-sm" data-testid="adaptation-table">
                        <thead className="bg-slate-50 text-slate-600">
                            <tr>
                                <th className="p-3 text-left">Сотрудник</th>
                                {columnVisible("position") ? <th className="p-3 text-left">Должность</th> : null}
                                <th className="p-3 text-left">Этап</th>
                                <th className="p-3 text-left">План / факт</th>
                                {columnVisible("progress") ? <th className="p-3 text-left">Ответы</th> : null}
                                <th className="p-3 text-left">Статус</th>
                                {columnVisible("risk") ? <th className="p-3 text-left">Итог / риск</th> : null}
                                <th className="p-3" />
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.length === 0 ? (
                                <tr>
                                    <td className="p-6 text-slate-500 text-center" colSpan={8}>
                                        {loading
                                            ? "Загрузка…"
                                            : showArchived
                                                ? "В архиве нет этапов за выбранный период."
                                                : "Нет этапов за период. Поставьте сотрудника на адаптацию — список берётся из ERP."}
                                    </td>
                                </tr>
                            ) : (
                            filtered.map((row) => (
                                <tr key={row.id} className="border-t border-slate-100" data-testid={`adaptation-row-${row.id}`}>
                                    <td className="p-3">
                                        <div className="flex items-center gap-2">
                                            {settings.show_photo && row.photo_url ? <img src={row.photo_url} alt="" className="w-9 h-9 rounded-full object-cover" /> : <span className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-xs font-semibold text-slate-600">{initials(row.full_name)}</span>}
                                            <span>
                                                <button
                                                    type="button"
                                                    className="block font-semibold text-left hover:underline"
                                                    onClick={() => navigate(`/tests/adaptation/case/${row.enrollment_id}`)}
                                                    data-testid={`adaptation-fio-${row.id}`}
                                                >
                                                    {row.full_name}
                                                </button>
                                                <small className="text-slate-500">Принят {formatDateRu(row.date_hired)}</small>
                                                {row.talk_hr ? (
                                                    <small className="block text-amber-700">Запрос разговора с HR</small>
                                                ) : null}
                                            </span>
                                        </div>
                                    </td>
                                    {columnVisible("position") ? (
                                        <td className="p-3">
                                            <span className="block">{row.position}</span>
                                            <small className="text-slate-500">{row.department}</small>
                                        </td>
                                    ) : null}
                                    <td className="p-3">
                                        <span className="inline-flex px-2 py-0.5 rounded-lg bg-slate-100 text-slate-700 text-xs">{row.kind_label}</span>
                                    </td>
                                    <td className="p-3">
                                        <b className="block">{formatDateRu(row.plan_date)}</b>
                                        <small className="text-slate-500">
                                            {row.fact_date ? `Факт: ${formatDateRu(row.fact_date)}` : "Факт пока отсутствует"}
                                        </small>
                                    </td>
                                    {columnVisible("progress") ? (
                                        <td className="p-3">
                                            <div className="flex gap-1">
                                                {(row.progress || []).map((dot) => (
                                                    <span
                                                        key={dot.role}
                                                        title={`${dot.role}: ${dot.state}`}
                                                        className={`w-7 h-7 rounded-full border text-xs font-semibold flex items-center justify-center ${DOT_CLASS[dot.state] || DOT_CLASS.waiting}`}
                                                    >
                                                        {dot.state === "muted" ? "—" : dot.label}
                                                    </span>
                                                ))}
                                            </div>
                                        </td>
                                    ) : null}
                                    <td className="p-3">
                                        <span className={`inline-flex px-2 py-0.5 rounded-lg text-xs font-medium ${STATUS_BADGE[row.status] || STATUS_BADGE.planned}`}>
                                            {row.status_label}
                                        </span>
                                    </td>
                                    {columnVisible("risk") ? (
                                        <td className="p-3">
                                            <b className="block">{row.outcome}</b>
                                            <small className={RISK_CLASS[row.risk] || RISK_CLASS.uncalculated}>Риск: {row.risk_label}</small>
                                        </td>
                                    ) : null}
                                    <td className="p-3">
                                        <div className="flex flex-col items-end gap-1">
                                            <button
                                                type="button"
                                                className="text-sm px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"
                                                onClick={() => navigate(`/tests/adaptation/${row.id}`)}
                                            >
                                                Открыть
                                            </button>
                                            {row.employee_take_token ? (
                                                <>
                                                    <a
                                                        href={row.employee_take_path || `/adaptation/forms/${row.employee_take_token}`}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        className="text-xs text-slate-500 hover:underline"
                                                    >
                                                        Открыть форму
                                                    </a>
                                                    <button
                                                        type="button"
                                                        className="text-xs text-slate-500 hover:underline"
                                                        onClick={async () => {
                                                            const url = adaptationFormAbsoluteUrl(row.employee_take_token);
                                                            const ok = await copyText(url);
                                                            showAlert(ok ? "Ссылка скопирована" : url, ok ? "success" : "info");
                                                        }}
                                                    >
                                                        Копировать ссылку
                                                    </button>
                                                </>
                                            ) : null}
                                        </div>
                                    </td>
                                </tr>
                            ))
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {showEnroll && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-start justify-center p-4 pt-16" data-testid="enroll-modal">
                    {createdTake ? (
                        <div className="bg-white rounded-2xl p-6 w-full max-w-lg space-y-4 shadow-xl">
                            <h2 className="text-lg font-semibold">Ссылки для прохождения</h2>
                            <p className="text-sm text-slate-500">
                                Скопируйте ссылку и отправьте сотруднику. После заполнения ответы сохранятся в его карточке адаптации.
                            </p>
                            <AdaptationTakeLinks
                                links={createdTake.links}
                                employeeId={createdTake.employee_id}
                                fullName={createdTake.full_name}
                                compact
                            />
                            <div className="flex justify-end gap-2">
                                {createdTake.enrollment_id ? (
                                    <button
                                        type="button"
                                        className="px-3 py-2 text-sm underline"
                                        onClick={() => {
                                            setShowEnroll(false);
                                            navigate(`/tests/adaptation/case/${createdTake.enrollment_id}`);
                                        }}
                                    >
                                        Открыть карточку
                                    </button>
                                ) : null}
                                <button type="button" className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm" onClick={() => setShowEnroll(false)}>Готово</button>
                            </div>
                        </div>
                    ) : (
                    <form onSubmit={submitEnroll} className="bg-white rounded-2xl p-6 w-full max-w-md space-y-3 shadow-xl">
                        <h2 className="text-lg font-semibold">Добавить сотрудника</h2>
                        <p className="text-sm text-slate-500">
                            Список: сотрудники штата и учётки ERP. Если человек уже в штате, постановка идёт по его карточке.
                        </p>
                        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={temporaryMode} onChange={(e) => setTemporaryMode(e.target.checked)} />Временный сотрудник (ещё нет в ERP)</label>
                        <fieldset className="text-sm space-y-1">
                            <legend className="text-slate-500 mb-1">Маршрут</legend>
                            <label className="flex items-center gap-2">
                                <input type="radio" name="enroll-route" checked={enrollRoute === "full"} onChange={() => setEnrollRoute("full")} />
                                Полный (1 неделя, 1 месяц, 2 месяца)
                            </label>
                            <label className="flex items-center gap-2">
                                <input type="radio" name="enroll-route" checked={enrollRoute === "control"} onChange={() => setEnrollRoute("control")} />
                                Контрольный (только HR через 2 месяца, без анкеты сотрудника)
                            </label>
                        </fieldset>
                        {!temporaryMode ? <><input
                            className="w-full border rounded-xl px-3 py-2 text-sm"
                            placeholder="Поиск по ФИО, роли, email"
                            value={enrollQuery}
                            onChange={(e) => setEnrollQuery(e.target.value)}
                            data-testid="enroll-search"
                        />
                        <div
                            className="border border-slate-200 rounded-xl overflow-y-auto max-h-64"
                            data-testid="enroll-employee"
                            role="listbox"
                            aria-label="Сотрудники ERP"
                        >
                            {enrollCandidates.length === 0 ? (
                                <p className="px-3 py-6 text-sm text-slate-400 text-center">Нет сотрудников ERP</p>
                            ) : (
                                enrollCandidates.map((h) => {
                                    const id = String(h.erp_user_id || h.id);
                                    const roleBit = h.position || h.department || h.role || "";
                                    const selected = enrollId === id;
                                    return (
                                        <button
                                            type="button"
                                            key={id}
                                            role="option"
                                            aria-selected={selected}
                                            data-testid={`enroll-employee-${id}`}
                                            className={`w-full text-left px-3 py-2.5 text-sm border-b border-slate-100 last:border-b-0 ${
                                                selected ? "bg-slate-900 text-white" : "bg-white hover:bg-slate-50 text-slate-800"
                                            }`}
                                            onClick={() => setEnrollId(id)}
                                        >
                                            <span className="block font-medium">{h.full_name || h.username}</span>
                                            {roleBit ? (
                                                <span className={`block text-xs mt-0.5 ${selected ? "text-slate-200" : "text-slate-500"}`}>
                                                    {roleBit}
                                                    {h.username ? ` · ${h.username}` : ""}
                                                </span>
                                            ) : null}
                                        </button>
                                    );
                                })
                            )}
                        </div></> : <div className="grid gap-2">
                            <input required className="border rounded-xl px-3 py-2" placeholder="ФИО" value={temporary.full_name} onChange={(e) => setTemporary({ ...temporary, full_name: e.target.value })} />
                            <input required className="border rounded-xl px-3 py-2" placeholder="Должность" value={temporary.position} onChange={(e) => setTemporary({ ...temporary, position: e.target.value })} />
                            <input required className="border rounded-xl px-3 py-2" placeholder="Отдел" value={temporary.department} onChange={(e) => setTemporary({ ...temporary, department: e.target.value })} />
                            <label className="text-sm text-slate-500">Подтверждённая дата выхода<input required type="date" className="block w-full border rounded-xl px-3 py-2 text-slate-900" value={temporary.start_date} onChange={(e) => setTemporary({ ...temporary, start_date: e.target.value })} /></label>
                            <input className="border rounded-xl px-3 py-2" placeholder="ERP ID руководителя" value={temporary.manager_user_id} onChange={(e) => setTemporary({ ...temporary, manager_user_id: e.target.value })} />
                            <input className="border rounded-xl px-3 py-2" placeholder="ФИО руководителя" value={temporary.manager_name} onChange={(e) => setTemporary({ ...temporary, manager_name: e.target.value })} />
                        </div>}
                        {enrollRoute === "full" ? (
                        <label className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={includeControl} onChange={(e) => setIncludeControl(e.target.checked)} />
                            В полном маршруте вместо опроса на 2 месяце — только контрольная точка HR
                        </label>
                        ) : null}
                        <div className="flex justify-end gap-2">
                            <button type="button" className="px-3 py-2 text-sm" onClick={() => setShowEnroll(false)}>Отмена</button>
                            <button type="submit" className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm" disabled={enrollLoading || (!temporaryMode && !enrollId)}>
                                {enrollLoading ? "Сохранение…" : "Поставить и получить ссылку"}
                            </button>
                        </div>
                    </form>
                    )}
                </div>
            )}

            {showSettings && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4" data-testid="adaptation-settings-modal">
                    <div className="bg-slate-50 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl">
                        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b bg-white px-6 py-5">
                            <div>
                                <h2 className="text-xl font-semibold text-slate-900">Настройки адаптации</h2>
                                <p className="mt-1 text-sm text-slate-500">Сроки, отображение таблицы и сообщения участникам адаптации.</p>
                            </div>
                            <button type="button" className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={() => setShowSettings(false)} aria-label="Закрыть настройки">✕</button>
                        </div>

                        <div className="space-y-5 p-6">
                            <section className="rounded-2xl border border-slate-200 bg-white p-5">
                                <h3 className="font-semibold text-slate-900">Сроки и отображение</h3>
                                <p className="mt-1 text-sm text-slate-500">Плановые этапы считаются от даты найма. Выходной переносится на ближайший рабочий день.</p>
                                <div className="mt-4 grid gap-4 md:grid-cols-2">
                                    <label className="flex items-start gap-3 rounded-xl bg-slate-50 p-3 text-sm"><input className="mt-0.5" type="checkbox" checked={settings.overdue_enabled} onChange={(e) => setSettings({ ...settings, overdue_enabled: e.target.checked })} /><span><b className="block text-slate-800">Контролировать просрочку</b><span className="text-slate-500">Отправлять уведомление на следующий день, если сотрудник не заполнил форму.</span></span></label>
                                    <label className="block text-sm text-slate-600">Когда считать форму просроченной<input type="time" className="block mt-1.5 w-full border rounded-xl px-3 py-2 text-slate-900 disabled:bg-slate-100" disabled={!settings.overdue_enabled} value={settings.overdue_time || "09:00"} onChange={(e) => setSettings({ ...settings, overdue_time: e.target.value })} /></label>
                                    <label className="block text-sm text-slate-600">Часовой пояс<input className="block mt-1.5 w-full border rounded-xl px-3 py-2 text-slate-900" value={settings.timezone || "Europe/Samara"} onChange={(e) => setSettings({ ...settings, timezone: e.target.value })} /></label>
                                    <label className="flex items-start gap-3 rounded-xl bg-slate-50 p-3 text-sm"><input className="mt-0.5" type="checkbox" checked={settings.show_photo} onChange={(e) => setSettings({ ...settings, show_photo: e.target.checked })} /><span><b className="block text-slate-800">Фотографии в таблице</b><span className="text-slate-500">Показывать фото сотрудника, если оно доступно.</span></span></label>
                                </div>
                                <fieldset className="mt-4 text-sm"><legend className="font-medium text-slate-700">Колонки таблицы</legend><div className="mt-2 flex flex-wrap gap-3">{OPTIONAL_COLUMNS.map(([key, label]) => <label key={key} className="flex items-center gap-2 rounded-lg border px-3 py-2"><input type="checkbox" checked={columnVisible(key)} onChange={() => toggleColumn(key)} />{label}</label>)}</div></fieldset>
                            </section>

                            <section className="rounded-2xl border border-slate-200 bg-white p-5">
                                <h3 className="font-semibold text-slate-900">Маршрут контакта для адаптации</h3>
                                <p className="mt-1 text-sm text-slate-500">Эти правила только определяют подходящего получателя. Автоматическая отправка в Telegram сейчас не выполняется.</p>
                                <div className="mt-4 grid gap-4 md:grid-cols-2">
                                    <label className="flex items-start gap-3 rounded-xl bg-slate-50 p-3 text-sm">
                                        <input className="mt-0.5" type="checkbox" checked={Boolean(settings.allow_personal_telegram_fallback)} onChange={(e) => setSettings({ ...settings, allow_personal_telegram_fallback: e.target.checked })} />
                                        <span><b className="block text-slate-800">Разрешить личный Telegram</b><span className="text-slate-500">Использовать подтверждённый личный контакт, только если нет персонального рабочего.</span></span>
                                    </label>
                                    <label className="block text-sm text-slate-600">Срок подтверждения ручной передачи, часов<input type="number" min="1" max="168" className="block mt-1.5 w-full border rounded-xl px-3 py-2 text-slate-900" value={settings.manual_share_confirmation_hours || 24} onChange={(e) => setSettings({ ...settings, manual_share_confirmation_hours: Number(e.target.value) || 24 })} /></label>
                                </div>
                                <p className="mt-3 text-xs text-slate-500">Если подходящего контакта нет, маршрут назначается ответственному HR, а при его отсутствии — роли HR. Общий контакт отдела не выбирается автоматически.</p>
                            </section>

                            <section>
                                <h3 className="font-semibold text-slate-900">Уведомления участникам</h3>
                                <p className="mt-1 text-sm text-slate-500">Ниже показан пример сообщения в том виде, в котором его увидит получатель.</p>
                                <div className="mt-3 space-y-3">
                                    {notificationTemplates.map((item, index) => {
                                        const key = `${item.audience}-${item.event}`;
                                        const isEditing = editingTemplate === key;
                                        return <article key={key} className={`rounded-2xl border bg-white p-4 ${item.enabled ? "border-slate-200" : "border-slate-200 opacity-70"}`} data-testid={`notification-template-${key}`}>
                                            <div className="flex flex-wrap items-start justify-between gap-3">
                                                <div><h4 className="font-medium text-slate-900">{NOTIFICATION_EVENT_LABELS[item.event] || "Уведомление"}</h4><p className="text-sm text-slate-500">{NOTIFICATION_AUDIENCE_LABELS[item.audience] || "Получателю"} · {NOTIFICATION_EVENT_HINTS[item.event] || "Системное уведомление по адаптации."}</p></div>
                                                <label className="flex items-center gap-2 text-sm font-medium text-slate-600"><input type="checkbox" checked={item.enabled} onChange={(e) => setNotificationTemplates((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, enabled: e.target.checked } : row))} />Отправлять</label>
                                            </div>
                                            {isEditing ? <div className="mt-3">
                                                <label className="text-sm font-medium text-slate-700">Текст сообщения<textarea className="mt-1.5 min-h-24 w-full border rounded-xl p-3 font-normal text-slate-900" value={item.text} onChange={(e) => setNotificationTemplates((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, text: e.target.value } : row))} /></label>
                                                <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500"><span>Доступные подстановки:</span>{TEMPLATE_VARIABLES.map(([token, label]) => <span key={token} className="rounded-md bg-slate-100 px-2 py-1" title={token}>{label}</span>)}</div>
                                                <button type="button" className="mt-3 text-sm font-medium text-slate-700 underline" onClick={() => setEditingTemplate("")}>Готово</button>
                                            </div> : <div className="mt-3 rounded-xl bg-slate-50 p-3">
                                                <p className="whitespace-pre-wrap text-sm text-slate-700">{notificationPreview(item.text)}</p>
                                                <button type="button" className="mt-2 text-xs font-medium text-[#3730a3] hover:underline" onClick={() => setEditingTemplate(key)}>Изменить текст</button>
                                            </div>}
                                        </article>;
                                    })}
                                </div>
                            </section>
                        </div>
                        {notificationErrors.length ? <section className="mx-6 mb-5 rounded-xl bg-red-50 p-3"><b className="text-sm text-red-800">Не удалось доставить уведомления</b>{notificationErrors.map((item) => <div key={item.id} className="mt-2 text-xs text-red-700">Этап #{item.checkpoint_id} · {NOTIFICATION_AUDIENCE_LABELS[item.role] || "Получателю"} · {NOTIFICATION_EVENT_LABELS[item.event] || "Уведомление"}: {item.last_error}<button type="button" className="ml-2 underline" onClick={() => retryNotification(item.id)}>Отправить ещё раз</button></div>)}</section> : null}
                        <div className="sticky bottom-0 flex justify-end gap-2 border-t bg-white px-6 py-4">
                            <button type="button" className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50" onClick={() => setShowSettings(false)} data-testid="adaptation-settings-cancel">Отменить</button>
                            <button type="button" className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-medium" onClick={saveSettings}>Сохранить изменения</button>
                        </div>
                    </div>
                </div>
            )}

            {showReport && report && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4" data-testid="report-modal">
                    <div className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto space-y-4">
                        <h2 className="text-lg font-semibold">Отчеты</h2>
                        {[['internal', 'Действующие сотрудники'], ['terminated', 'Уволенные сотрудники']].map(([key, title]) => (
                            <section key={key} className={key === 'terminated' ? 'bg-slate-100 p-3 rounded-xl' : ''}>
                                <h3 className="font-medium">{title}</h3>
                                <div className="overflow-x-auto"><table className="w-full text-sm">
                                    <thead><tr>{['Сотрудник', 'Должность', 'Этап', 'План', 'Факт', 'Итог', 'Риск', 'Документы'].map(label => <th key={label} className="p-2 text-left">{label}</th>)}</tr></thead>
                                    <tbody>{(report[key] || []).map((item, index) => <tr key={index}>
                                        <td className="p-2">{item.employee}</td><td>{item.position}</td><td>{item.stage}</td>
                                        <td>{formatDateRu(item.plan_date)}</td><td>{item.fact_date ? formatDateRu(item.fact_date) : '—'}</td>
                                        <td>{item.outcome}</td><td>{item.risk}</td>
                                        <td>{item.enrollment_id ? <button className="underline" onClick={() => navigate(`/tests/adaptation/case/${item.enrollment_id}`)}>Открыть</button> : '—'}</td>
                                    </tr>)}</tbody>
                                </table></div>
                                {!(report[key] || []).length ? <p className="text-sm text-slate-500">Нет этапов за выбранный месяц</p> : null}
                            </section>
                        ))}
                        <section>
                            <h3 className="font-medium text-sm mb-1">Безопасно для руководителя</h3>
                            <ul className="text-sm space-y-1">
                                {(report.manager_safe || []).map((r, i) => (
                                    <li key={i}>{r.employee}: {r.hr_notes}</li>
                                ))}
                            </ul>
                        </section>
                        <div className="flex justify-end">
                            <button type="button" className="px-4 py-2 rounded-xl border" onClick={() => setShowReport(false)}>Закрыть</button>
                        </div>
                    </div>
                </div>
            )}
        </MainLayout>
    );
}
