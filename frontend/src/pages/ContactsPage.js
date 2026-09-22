import { useEffect, useState } from "react";
import MainLayout from "../layout/MainLayout";
import {
    getCompanyContacts,
    createCompanyContact,
    deleteCompanyContact,
} from "../services/hrOpsApi";
import { useAlertContext } from "../context/AlertContext";
import { useAuth } from "../context/AuthContext";

export default function ContactsPage() {
    const { showAlert } = useAlertContext();
    const { user } = useAuth();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ name: "", email: "", phone_number: "" });
    const [saving, setSaving] = useState(false);

    const load = async () => {
        try {
            setLoading(true);
            const data = await getCompanyContacts();
            setItems(Array.isArray(data) ? data : []);
        } catch (e) {
            showAlert(`Не удалось загрузить контакты: ${e.message || e}`, "error");
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleCreate = async (e) => {
        e.preventDefault();
        if (!form.name.trim()) {
            showAlert("Укажите имя контакта", "warning");
            return;
        }
        const phones = form.phone_number
            .split(",")
            .map((p) => p.trim())
            .filter(Boolean);
        if (!phones.length) {
            showAlert("Укажите телефон в формате +7XXXXXXXXXX", "warning");
            return;
        }
        try {
            setSaving(true);
            await createCompanyContact({
                hr_id: user?.erp_user_id || user?.id || null,
                name: form.name.trim(),
                email: form.email.trim() || null,
                phone_number: phones,
            });
            setForm({ name: "", email: "", phone_number: "" });
            showAlert("Контакт добавлен — он будет использоваться при публикации на HH", "success");
            await load();
        } catch (err) {
            showAlert(`Ошибка: ${err.message || err}`, "error");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Удалить контакт?")) return;
        try {
            await deleteCompanyContact(id);
            await load();
        } catch (err) {
            showAlert(`Не удалось удалить: ${err.message || err}`, "error");
        }
    };

    return (
        <MainLayout className="p-6">
            <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">Контакты для HH.ru</h1>
            <p className="text-sm text-slate-500 mb-6">
                Первый контакт в списке подставляется в публикацию вакансий на HH.ru вместо тестовых данных.
            </p>

            <form onSubmit={handleCreate} className="bg-white border border-slate-200/60 rounded-2xl p-4 mb-6 grid gap-3 md:grid-cols-4">
                <input
                    className="border border-slate-200 rounded-xl px-3 py-2 text-sm"
                    placeholder="Имя"
                    value={form.name}
                    onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                />
                <input
                    className="border border-slate-200 rounded-xl px-3 py-2 text-sm"
                    placeholder="Email"
                    value={form.email}
                    onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
                />
                <input
                    className="border border-slate-200 rounded-xl px-3 py-2 text-sm"
                    placeholder="Телефоны через запятую"
                    value={form.phone_number}
                    onChange={(e) => setForm((p) => ({ ...p, phone_number: e.target.value }))}
                />
                <button
                    type="submit"
                    disabled={saving}
                    className="bg-slate-900 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-50"
                >
                    {saving ? "..." : "Добавить"}
                </button>
            </form>

            {loading ? (
                <p className="text-slate-500">Загрузка...</p>
            ) : items.length === 0 ? (
                <p className="text-slate-500">Контактов пока нет.</p>
            ) : (
                <div className="space-y-3">
                    {items.map((c, idx) => (
                        <div key={c.id} className="bg-white border border-slate-200/60 rounded-2xl p-4 flex justify-between gap-4">
                            <div>
                                <div className="font-semibold text-slate-900">
                                    {c.name}{idx === 0 && <span className="ml-2 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">основной</span>}
                                </div>
                                <div className="text-sm text-slate-600">{c.email || "без email"}</div>
                                <div className="text-sm text-slate-500">{(c.phone_number || []).join(", ")}</div>
                            </div>
                            <button type="button" onClick={() => handleDelete(c.id)} className="text-sm text-red-600">
                                Удалить
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </MainLayout>
    );
}
