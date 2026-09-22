import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import MainLayout from "../layout/MainLayout";
import ContactEditor from "../components/employees/ContactEditor";
import {
    createEmployeeContact,
    deactivateContact,
    getEmployee,
    getEmployeeContacts,
    updateContact,
    updateEmployee,
} from "../services/hrOpsApi";
import { useAlertContext } from "../context/AlertContext";
import { useAuth } from "../context/AuthContext";
import { formatDateRu } from "../utils/dateFormat";

const HR_ROLES = ["superadmin", "admin", "manager", "senior_manager", "hr", "owner", "dev", "tech_admin", "director"];

export default function EmployeeDetailPage() {
    const { employeeId } = useParams();
    const { showAlert } = useAlertContext();
    const { user } = useAuth();
    const canManage = HR_ROLES.includes(String(user?.role || "").toLowerCase());
    const [employee, setEmployee] = useState(null);
    const [contacts, setContacts] = useState([]);
    const [workStartDate, setWorkStartDate] = useState("");
    const [savingDate, setSavingDate] = useState(false);

    const load = useCallback(async () => {
        const loadedEmployee = await getEmployee(employeeId);
        setEmployee(loadedEmployee);
        setWorkStartDate(loadedEmployee?.date_hired || "");
        if (canManage) setContacts(await getEmployeeContacts(employeeId) || []);
    }, [employeeId, canManage]);

    useEffect(() => {
        load().catch((error) => showAlert(error.message, "error"));
    }, [load, showAlert]);

    const mutateContacts = async (operation) => {
        try {
            await operation();
            await load();
            showAlert("Контакты обновлены", "success");
        } catch (error) {
            showAlert(error.message, "error");
        }
    };

    const saveWorkStartDate = async (event) => {
        event.preventDefault();
        if (!workStartDate) {
            showAlert("Укажите дату выхода на работу", "error");
            return;
        }
        setSavingDate(true);
        try {
            const updated = await updateEmployee(employeeId, { date_hired: workStartDate });
            setEmployee(updated);
            setWorkStartDate(updated.date_hired);
            showAlert("Дата выхода на работу сохранена", "success");
        } catch (error) {
            showAlert(error.message, "error");
        } finally {
            setSavingDate(false);
        }
    };

    return (
        <MainLayout>
            <Link to="/employees" className="text-sm text-slate-500">← Сотрудники</Link>
            {!employee ? <p className="mt-5">Загрузка…</p> : (
                <div className="mt-4 space-y-4">
                    <header>
                        <h1 className="text-3xl font-bold">{employee.full_name}</h1>
                        <p className="text-slate-500">{employee.position} · {employee.department}</p>
                    </header>

                    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                        <div className="flex flex-wrap items-end justify-between gap-4">
                            <div>
                                <h2 className="text-lg font-semibold text-slate-900">Трудоустройство</h2>
                                <p className="mt-1 text-sm text-slate-500">
                                    Дата выхода: <b className="text-slate-700">{formatDateRu(employee.date_hired)}</b>
                                </p>
                            </div>
                            {canManage ? (
                                <form className="flex flex-wrap items-end gap-3" onSubmit={saveWorkStartDate}>
                                    <label className="text-sm">
                                        <span className="mb-1.5 block font-semibold text-slate-700">Дата выхода на работу</span>
                                        <input
                                            type="date"
                                            required
                                            value={workStartDate}
                                            onChange={(event) => setWorkStartDate(event.target.value)}
                                            className="rounded-xl border border-slate-200 px-4 py-2.5 focus:border-[#4f46e5] focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/40"
                                            data-testid="employee-work-start-date"
                                        />
                                    </label>
                                    <button
                                        type="submit"
                                        disabled={savingDate || workStartDate === employee.date_hired}
                                        className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                                        data-testid="save-employee-work-start-date"
                                    >
                                        {savingDate ? "Сохранение…" : "Сохранить дату"}
                                    </button>
                                </form>
                            ) : null}
                        </div>
                    </section>

                    {canManage ? (
                        <ContactEditor
                            contacts={contacts}
                            onCreate={(data) => mutateContacts(() => createEmployeeContact(employeeId, data))}
                            onUpdate={(id, data) => mutateContacts(() => updateContact(id, data))}
                            onDeactivate={(id) => mutateContacts(() => deactivateContact(id))}
                        />
                    ) : (
                        <p className="rounded-xl border bg-white p-4 text-sm text-slate-500">
                            Персональные контакты доступны только HR и администраторам.
                        </p>
                    )}
                </div>
            )}
        </MainLayout>
    );
}
