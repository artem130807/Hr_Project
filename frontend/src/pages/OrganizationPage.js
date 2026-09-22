import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import MainLayout from "../layout/MainLayout";
import { getOrganizationDepartments } from "../services/hrOpsApi";

export default function OrganizationPage() {
    const [items, setItems] = useState([]);
    useEffect(() => { getOrganizationDepartments().then(setItems).catch(() => setItems([])); }, []);
    return <MainLayout><h1 className="text-3xl font-bold">Структура компании</h1><p className="mt-1 text-slate-500">Отделы, сотрудники и общие рабочие контакты.</p><div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{items.map((item) => <Link key={item.id} to={`/organization/departments/${item.id}`} className="rounded-2xl border bg-white p-5 hover:shadow"><h2 className="text-lg font-semibold">{item.name}</h2><p className="text-sm text-slate-500">Руководитель: {item.lead_name || "не указан"}</p><p className="mt-3 text-sm">Сотрудников: <b>{item.employee_count}</b></p></Link>)}</div></MainLayout>;
}
