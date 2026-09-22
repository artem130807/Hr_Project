import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import MainLayout from "../layout/MainLayout";
import ContactEditor from "../components/employees/ContactEditor";
import { createDepartmentContact, deactivateContact, getOrganizationDepartment, updateContact } from "../services/hrOpsApi";
import { useAlertContext } from "../context/AlertContext";
import { useAuth } from "../context/AuthContext";

const CONTACT_ADMIN_ROLES = ["superadmin", "admin", "manager", "senior_manager", "hr", "owner", "dev", "tech_admin", "director"];

export default function DepartmentDetailPage() {
    const { departmentId } = useParams(); const { showAlert } = useAlertContext(); const { user } = useAuth(); const [data, setData] = useState(null);
    const canManageContacts = CONTACT_ADMIN_ROLES.includes(user?.role);
    const load = useCallback(() => getOrganizationDepartment(departmentId).then(setData), [departmentId]);
    useEffect(() => { load().catch((e) => showAlert(e.message, "error")); }, [load, showAlert]);
    const mutate = async (operation) => { try { await operation(); await load(); showAlert("Контакты отдела обновлены", "success"); } catch (e) { showAlert(e.message, "error"); } };
    return <MainLayout><Link to="/organization" className="text-sm text-slate-500">← Структура компании</Link>{data ? <div className="mt-4 space-y-5"><header><h1 className="text-3xl font-bold">{data.name}</h1><p className="text-slate-500">Руководитель: {data.lead_name || "не указан"}</p></header><section className="rounded-2xl border bg-white p-5"><h2 className="text-lg font-semibold">Сотрудники отдела</h2><div className="mt-3 divide-y">{data.employees.map((e) => <Link className="block py-3 hover:underline" key={e.id} to={`/employees/${e.id}`}>{e.full_name} · {e.position}</Link>)}</div></section><ContactEditor departmentMode readOnly={!canManageContacts} contacts={data.contacts} onCreate={(payload) => mutate(() => createDepartmentContact(departmentId, { ...payload, usage_type: "shared", allow_adaptation: false, is_primary: false }))} onUpdate={(id, payload) => mutate(() => updateContact(id, payload))} onDeactivate={(id) => mutate(() => deactivateContact(id))} /></div> : <p className="mt-5">Загрузка…</p>}</MainLayout>;
}
