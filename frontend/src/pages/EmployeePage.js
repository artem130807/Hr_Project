import {useEffect, useMemo, useState} from "react";
import {getUsers} from "../services/userApi";
import {getHiredEmployees, deleteEmployee, createEmployee, getVnrHires} from "../services/hrOpsApi";
import EmployeeTable from "../components/employess/EmployeeTable";
import EmployeeForm from "../components/employess/EmployeeForm";
import EmployeeStatsModal from "../components/employees/EmployeeStatsModal";
import HiredEmployeeForm from "../components/employees/HiredEmployeeForm";
import {exportEmployeesToExcel} from "../utils/excelUtils";
import {DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors} from "@dnd-kit/core";
import {arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy} from "@dnd-kit/sortable";
import {useAlertContext} from "../context/AlertContext";
import MainLayout from "../layout/MainLayout";
import { formatDateRu } from "../utils/dateFormat";
import { useNavigate } from "react-router-dom";


export default function EmployeePage() {
    const navigate = useNavigate();
    // all = unified directory; panel = ERP logins; hired = local HR staffing records.
    const [tab, setTab] = useState("all");
    const [employees, setEmployees] = useState([])
    const [hired, setHired] = useState([])
    const [statsEmployee, setStatsEmployee] = useState(null)
    const [loading, setLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')
    const [showCreateForm, setShowCreateForm] = useState(false)
    const [showPanelForm, setShowPanelForm] = useState(false)
    const [editingPanelUser, setEditingPanelUser] = useState(null)
    const [creating, setCreating] = useState(false)
    const {showAlert} = useAlertContext()

    const fetchEmployees = async (manageLoading = true) => {
        try {
            if (manageLoading) setLoading(true);
            const data = await getUsers();
            setEmployees(Array.isArray(data) ? data : []);
        } catch (e) {
            console.error("Ошибка загрузки сотрудников:", e);
            showAlert(`Не удалось загрузить пользователей панели: ${e.message || e}`, "error");
            setEmployees([]);
        } finally {
            if (manageLoading) setLoading(false);
        }
    };

    const fetchHired = async (manageLoading = true) => {
        try {
            if (manageLoading) setLoading(true);
            const [vnr, employees] = await Promise.all([
                getVnrHires({ activeOnly: true }),
                getHiredEmployees(),
            ]);
            const employeeById = new Map(
                (Array.isArray(employees) ? employees : []).map((employee) => [employee.id, employee])
            );
            const vnrRows = (Array.isArray(vnr) ? vnr : []).map((v) => ({
                id: v.employee_id ? `emp-${v.employee_id}` : `vnr-${v.id}`,
                vnr_id: v.id,
                employee_id: v.employee_id,
                erp_user_id: employeeById.get(v.employee_id)?.erp_user_id || null,
                candidate_id: v.candidate_id,
                full_name: v.full_name,
                department: v.department,
                position: v.position,
                date_hired: employeeById.get(v.employee_id)?.date_hired || v.hired_at,
                phone_number: employeeById.get(v.employee_id)?.phone_number || null,
                hr_user_id: v.hr_user_id,
                hr_user_name: v.hr_user_name,
                fromVnr: true,
            }));
            const vnrEmpIds = new Set(vnrRows.map((r) => r.employee_id).filter(Boolean));
            const extra = (Array.isArray(employees) ? employees : [])
                .filter((e) => !vnrEmpIds.has(e.id))
                .map((e) => ({ ...e, fromVnr: false }));
            setHired([...vnrRows, ...extra]);
        } catch (e) {
            showAlert(`Не удалось загрузить нанятых: ${e.message || e}`, "error");
            setHired([]);
        } finally {
            if (manageLoading) setLoading(false);
        }
    };

    useEffect(() => {
        setSearchQuery("");
        if (tab === "all") {
            setLoading(true);
            Promise.all([fetchEmployees(false), fetchHired(false)]).finally(() => setLoading(false));
        } else if (tab === "panel") fetchEmployees();
        else fetchHired();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tab])


    const handleAddEmployee = () => {
        setEditingPanelUser(null);
        setShowPanelForm(true);
    }

    const handleCreateHired = async (payload) => {
        setCreating(true);
        try {
            const created = await createEmployee(payload);
            setHired((prev) => [{ ...created, fromVnr: false }, ...prev]);
            setShowCreateForm(false);
            showAlert("Сотрудник добавлен в штат HR", "success");
        } catch (e) {
            showAlert(e.message || String(e), "error");
            throw e;
        } finally {
            setCreating(false);
        }
    };

    const handlePanelUserAdded = (user) => {
        if (user?.id) {
            setEmployees((prev) => {
                const without = prev.filter((u) => String(u.id) !== String(user.id));
                return [user, ...without];
            });
        } else {
            fetchEmployees();
        }
        setShowPanelForm(false);
        setEditingPanelUser(null);
        // The backend synchronizes an ERP user's work-start date to the linked
        // HR employee. Reload the HR side as well, otherwise the unified row
        // keeps rendering the stale local date until a full page refresh.
        void fetchHired(false);
    };

    const handleEmployeeEdit = (employee) => {
        setEditingPanelUser(employee);
        setShowPanelForm(true);
    }

    const handleEmployeeStats = (employee) => {
        setStatsEmployee(employee)
    }

    const handleEmployeeDeleted = async () => {
        showAlert(
            "Удаление пользователей панели пока выполняется в ERP.",
            "warning"
        );
    }

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    )

    const handleDragEnd = (event) => {
        const {active, over} = event;
        if (!over || active.id === over.id) return;

        setEmployees((items) => {
            const oldIndex = items.findIndex((item) => item.id === active.id)
            const newIndex = items.findIndex((item) => item.id === over.id)
            if (oldIndex < 0 || newIndex < 0) return items;
            return arrayMove(items, oldIndex, newIndex)
        })
    }

    const filteredEmployees = employees.filter(emp => {
        if (!searchQuery) return true;

        const query = searchQuery.toLowerCase();
        return (
            (emp.full_name && emp.full_name.toLowerCase().includes(query)) ||
            (emp.name && emp.name.toLowerCase().includes(query)) ||
            (emp.username && emp.username.toLowerCase().includes(query)) ||
            (emp.role && emp.role.toLowerCase().includes(query)) ||
            (emp.department && emp.department.toLowerCase().includes(query))
        );
    });

    const filteredHired = hired.filter((h) => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return (
            (h.full_name && h.full_name.toLowerCase().includes(query)) ||
            (h.department && h.department.toLowerCase().includes(query)) ||
            (h.position && h.position.toLowerCase().includes(query)) ||
            (h.hr_user_name && h.hr_user_name.toLowerCase().includes(query))
        );
    });

    const directoryEmployees = useMemo(() => {
        const localByErpId = new Map(
            hired
                .filter((item) => item.erp_user_id)
                .map((item) => [String(item.erp_user_id), item])
        );
        const linkedLocalIds = new Set();
        const erpRows = employees.map((employee) => {
            const erpId = String(employee.erp_user_id || employee.id);
            const local = localByErpId.get(erpId);
            if (local) linkedLocalIds.add(String(local.id));
            return {
                key: `erp-${erpId}`,
                full_name: employee.full_name || employee.name || employee.username,
                department: employee.department || local?.department || "—",
                position: employee.position || local?.position || "—",
                contact: employee.username || local?.phone_number || "—",
                date_hired: local?.date_hired || employee.date_hired || null,
                sources: local ? ["ERP", "HR-платформа"] : ["ERP"],
                erp: employee,
                local,
            };
        });
        const localRows = hired
            .filter((item) => !linkedLocalIds.has(String(item.id)))
            .map((item) => ({
                key: `hr-${item.id}`,
                full_name: item.full_name,
                department: item.department || "—",
                position: item.position || "—",
                contact: item.phone_number || "—",
                date_hired: item.date_hired,
                sources: [item.fromVnr ? "HR-платформа · ВНР" : "HR-платформа"],
                erp: null,
                local: item,
            }));
        return [...erpRows, ...localRows];
    }, [employees, hired]);

    const filteredDirectoryEmployees = directoryEmployees.filter((employee) => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return `${employee.full_name || ""} ${employee.department || ""} ${employee.position || ""} ${employee.contact || ""} ${employee.sources.join(" ")}`
            .toLowerCase()
            .includes(query);
    });

    const removeLocalEmployee = async (row) => {
        const local = row.local;
        const employeeId = local?.employee_id || (!local?.fromVnr ? local?.id : null);
        if (!employeeId) {
            showAlert("Запись ВНР управляется через статус кандидата и не удаляется из этой таблицы.", "warning");
            return;
        }
        if (!window.confirm("Удалить локальную запись сотрудника из HR-платформы?")) return;
        try {
            await deleteEmployee(employeeId);
            setHired((prev) => prev.filter((item) => item.id !== local.id));
            showAlert("Локальная запись сотрудника удалена", "success");
        } catch (error) {
            showAlert(error.message || String(error), "error");
        }
    };

    const handleExport = () => {
        exportEmployeesToExcel(tab === "all" ? directoryEmployees : employees)
    }

    const handleImport = () => {
        showAlert(
            "Импорт пользователей панели отключён — создавайте учётки кнопкой «Добавить пользователя».",
            "warning"
        );
    }

    return (
        <MainLayout>
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Сотрудники</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        {tab === "all"
                            ? "Единый список сотрудников из ERP и базы HR-платформы."
                            : tab === "panel"
                                ? "Учётные записи ERP с доступом к рабочим системам."
                                : "Локальные карточки сотрудников и нанятые кандидаты."}
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                {tab !== "panel" ? (
                    <button
                        type="button"
                        onClick={() => setShowCreateForm(true)}
                        className="bg-slate-900 text-white px-4 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
                        data-testid="add-hired-employee"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                        Добавить сотрудника
                    </button>
                ) : null}
                {tab !== "hired" ? (
                <button 
                    onClick={handleAddEmployee}
                    className="bg-white text-slate-700 border border-slate-200 px-4 py-2.5 rounded-xl hover:bg-slate-50 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
                    data-testid="add-panel-user"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                    Создать учётную запись ERP
                </button>
                ) : null}
                </div>
            </div>

            <div className="flex gap-4 mb-6 border-b border-slate-200">
                <button
                    type="button"
                    onClick={() => setTab("all")}
                    className={`pb-3 px-2 text-sm font-medium relative ${tab === "all" ? "text-[#4f46e5]" : "text-slate-500"}`}
                    data-testid="tab-all"
                >
                    Все сотрудники
                    {tab === "all" && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4f46e5]" />}
                </button>
                <button
                    type="button"
                    onClick={() => setTab("panel")}
                    className={`pb-3 px-2 text-sm font-medium relative ${tab === "panel" ? "text-[#4f46e5]" : "text-slate-500"}`}
                    data-testid="tab-panel"
                >
                    Только ERP
                    {tab === "panel" && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4f46e5]" />}
                </button>
                <button
                    type="button"
                    onClick={() => setTab("hired")}
                    className={`pb-3 px-2 text-sm font-medium relative ${tab === "hired" ? "text-[#4f46e5]" : "text-slate-500"}`}
                    data-testid="tab-hired"
                >
                    Только HR-платформа
                    {tab === "hired" && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4f46e5]" />}
                </button>
            </div>

            {tab === "all" ? (
                <div className="space-y-4">
                    <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200/60 flex flex-wrap gap-3 items-center">
                        <div className="flex-1 min-w-[240px]">
                            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Поиск</label>
                            <input
                                type="text"
                                placeholder="ФИО, отдел, должность, логин или источник…"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50"
                                data-testid="all-employees-search"
                            />
                        </div>
                        <div className="self-end pb-2 text-sm text-slate-500">Найдено: <b className="text-slate-800">{filteredDirectoryEmployees.length}</b></div>
                    </div>
                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-x-auto" data-testid="all-employees-table">
                        <table className="min-w-full text-sm">
                            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                                <tr>
                                    <th className="p-4 text-left">Сотрудник</th>
                                    <th className="p-4 text-left">Источник</th>
                                    <th className="p-4 text-left">Отдел</th>
                                    <th className="p-4 text-left">Должность</th>
                                    <th className="p-4 text-left">Логин / телефон</th>
                                    <th className="p-4 text-left">Дата выхода</th>
                                    <th className="p-4 text-right">Действия</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? <tr><td colSpan={7} className="p-8 text-center text-slate-400">Загрузка сотрудников…</td></tr> : null}
                                {!loading && filteredDirectoryEmployees.length === 0 ? <tr><td colSpan={7} className="p-8 text-center text-slate-400">{searchQuery ? "По вашему запросу ничего не найдено" : "Сотрудников пока нет"}</td></tr> : null}
                                {!loading && filteredDirectoryEmployees.map((employee) => <tr key={employee.key} className="border-t border-slate-100 hover:bg-slate-50/70">
                                    <td className="p-4"><div className="flex items-center gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 font-semibold text-slate-600">{(employee.full_name || "С").charAt(0).toUpperCase()}</span>{employee.local?.id ? <button type="button" className="font-medium text-slate-900 hover:underline" onClick={() => navigate(`/employees/${employee.local.id}`)}>{employee.full_name}</button> : <span className="font-medium text-slate-900">{employee.full_name}</span>}</div></td>
                                    <td className="p-4"><div className="flex flex-wrap gap-1">{employee.sources.map((source) => <span key={source} className={`rounded-full px-2 py-1 text-xs font-medium ${source.startsWith("ERP") ? "bg-teal-50 text-teal-700" : "bg-amber-50 text-amber-700"}`}>{source}</span>)}</div></td>
                                    <td className="p-4 text-slate-600">{employee.department}</td>
                                    <td className="p-4 text-slate-600">{employee.position}</td>
                                    <td className="p-4 text-slate-600">{employee.contact}</td>
                                    <td className="p-4 text-slate-600">{formatDateRu(employee.date_hired)}</td>
                                    <td className="p-4 text-right"><div className="flex justify-end gap-3">
                                        {employee.erp ? <button type="button" className="text-xs font-medium text-slate-600 hover:text-slate-900" onClick={() => handleEmployeeEdit(employee.erp)}>Редактировать ERP</button> : null}
                                        {employee.local ? <button type="button" className="text-xs font-medium text-red-600 hover:text-red-800" onClick={() => removeLocalEmployee(employee)}>Удалить из HR</button> : null}
                                    </div></td>
                                </tr>)}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : tab === "hired" ? (
                <div className="space-y-4">
                    <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200/60">
                        <input
                            type="text"
                            placeholder="Поиск по ФИО, отделу, должности…"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50"
                            data-testid="hired-search"
                        />
                    </div>
                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-hidden" data-testid="hired-employees-table">
                        <table className="min-w-full text-sm">
                            <thead className="bg-slate-50 text-slate-600">
                                <tr>
                                    <th className="p-3 text-left">ФИО</th>
                                    <th className="p-3 text-left">Отдел</th>
                                    <th className="p-3 text-left">Должность</th>
                                    <th className="p-3 text-left">Дата выхода</th>
                                    <th className="p-3 text-left">HR</th>
                                    <th className="p-3 text-left">Кандидат</th>
                                    <th className="p-3"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr><td className="p-4 text-slate-400" colSpan={7}>Загрузка…</td></tr>
                                ) : filteredHired.length === 0 ? (
                                    <tr>
                                        <td className="p-6 text-slate-400 text-center" colSpan={7}>
                                            {searchQuery
                                                ? "Никого не найдено"
                                                : "Пока нет записей штата — наймите кандидата (статус ВНР) или добавьте вручную."}
                                        </td>
                                    </tr>
                                ) : filteredHired.map((h) => (
                                    <tr key={h.id} className="border-t border-slate-100">
                                        <td className="p-3 font-medium">{(h.employee_id || (!h.fromVnr && h.id)) ? <button type="button" className="hover:underline" onClick={() => navigate(`/employees/${h.employee_id || h.id}`)}>{h.full_name}</button> : h.full_name}</td>
                                        <td className="p-3">{h.department}</td>
                                        <td className="p-3">{h.position}</td>
                                        <td className="p-3">{formatDateRu(h.date_hired)}</td>
                                        <td className="p-3">{h.hr_user_name || "—"}</td>
                                        <td className="p-3">{h.candidate_id ? `#${h.candidate_id}` : "—"}</td>
                                        <td className="p-3 text-right">
                                            <button
                                                type="button"
                                                className="text-red-600 text-xs"
                                                onClick={async () => {
                                                    if (!window.confirm("Удалить запись сотрудника?")) return;
                                                    const employeeId = h.employee_id || (!h.fromVnr ? h.id : null);
                                                    if (!employeeId) {
                                                        showAlert("Запись ВНР удаляется сменой статуса кандидата, не из штата.", "warning");
                                                        return;
                                                    }
                                                    try {
                                                        await deleteEmployee(employeeId);
                                                        setHired((prev) => prev.filter((x) => x.id !== h.id));
                                                        showAlert("Сотрудник удалён", "success");
                                                    } catch (e) {
                                                        showAlert(e.message || String(e), "error");
                                                    }
                                                }}
                                            >
                                                Удалить
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
            <>
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200/60 flex flex-wrap gap-4 items-end mb-6">
                <div className="flex-1 min-w-[200px]">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Поиск</label>
                    <div className="relative">
                        <input
                            type="text"
                            placeholder="Поиск по ФИО, логину, роли или отделу..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                        />
                        <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-slate-400">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <button 
                        onClick={handleExport}
                        className="bg-white border border-slate-200 text-slate-700 px-4 py-2.5 rounded-xl hover:bg-slate-50 transition-colors shadow-sm text-sm font-medium flex items-center gap-2 h-[42px]"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4-4m4 4V4" /></svg>
                        Экспорт (Excel)
                    </button>
                    
                    <div className="relative">
                        <button
                            type="button"
                            onClick={handleImport}
                            className="flex items-center gap-2 border border-slate-200 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors shadow-sm h-[42px] bg-white text-slate-700 hover:bg-slate-50"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                            Импорт (Excel)
                        </button>
                    </div>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center items-center py-20 text-slate-400">
                    <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Загрузка сотрудников...
                </div>
            ) : filteredEmployees.length > 0 ? (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-hidden">
                    <DndContext
                        sensors={sensors}
                        collisionDetection={closestCenter}
                        onDragEnd={handleDragEnd}
                    >
                        <SortableContext
                            items={filteredEmployees.map(e => e.id)}
                            strategy={verticalListSortingStrategy}
                        >
                            <EmployeeTable
                                employees={filteredEmployees}
                                onEmployeeEdit={handleEmployeeEdit}
                                onEmployeeDeleted={handleEmployeeDeleted}
                                onEmployeeStats={handleEmployeeStats}
                            />
                        </SortableContext>
                    </DndContext>
                </div>
            ) : (
                <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 018 0z" /></svg>
                    </div>
                    <h3 className="text-lg font-medium text-slate-800">
                        {searchQuery ? "Никого не найдено" : "Пользователей панели пока нет"}
                    </h3>
                    <p className="text-slate-500 mt-1 max-w-md">
                        {searchQuery
                            ? "Попробуйте изменить параметры поиска."
                            : "Создайте учётку кнопкой «Добавить пользователя» — запись появится в ERP и здесь."}
                    </p>
                </div>
            )}

            {statsEmployee && (
                <EmployeeStatsModal 
                    employee={statsEmployee} 
                    onClose={() => setStatsEmployee(null)} 
                />
            )}
            </>
            )}

            {showCreateForm && (
                <HiredEmployeeForm
                    onClose={() => setShowCreateForm(false)}
                    onSubmit={handleCreateHired}
                    isLoading={creating}
                />
            )}

            {showPanelForm && (
                <div
                    className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
                    onClick={() => {
                        setShowPanelForm(false);
                        setEditingPanelUser(null);
                    }}
                    data-testid="panel-user-form-overlay"
                >
                    <div
                        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <EmployeeForm
                            initialData={editingPanelUser || undefined}
                            onClose={() => {
                                setShowPanelForm(false);
                                setEditingPanelUser(null);
                            }}
                            onEmployeeAdded={handlePanelUserAdded}
                        />
                    </div>
                </div>
            )}
        </MainLayout>
    )
}
