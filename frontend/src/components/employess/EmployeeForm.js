import {useEffect, useState} from "react";
import { createUser, updateUser, getAdminRoles, resetUserPassword } from "../../services/userApi";
import {useAlertContext} from "../../context/AlertContext";
import {DEPARTMENTS} from "../../config/api";

const FALLBACK_ROLES = [
    { role: "hr", name: "HR" },
    { role: "owner", name: "Owner" },
    { role: "lead", name: "Lead" },
    { role: "manager", name: "Менеджер" },
    { role: "dev", name: "Dev" },
    { role: "art", name: "Art" },
];

export default function EmployeeForm({initialData , onClose, onEmployeeAdded }) {
    const isEdit = Boolean(initialData?.id);
    const [formData, setFormData] = useState({
        username: initialData?.username || "",
        password: "",
        name: initialData?.full_name || initialData?.name || "",
        role: initialData?.role || "hr",
        department: initialData?.department || null,
        date_hired: initialData?.date_hired || "",
    })
    const [roles, setRoles] = useState(FALLBACK_ROLES);
    const [saving, setSaving] = useState(false);
    const [resetting, setResetting] = useState(false);
    const {showAlert} = useAlertContext();

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const raw = await getAdminRoles();
                if (cancelled || !Array.isArray(raw) || raw.length === 0) return;
                const mapped = raw
                    .map((r) => ({
                        role: r.role || String(r.name || "").toLowerCase(),
                        name: r.name || r.role,
                    }))
                    .filter((r) => r.role);
                if (mapped.length) setRoles(mapped);
            } catch {
                /* keep fallback */
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    }

    const handleResetPassword = async () => {
        if (!initialData?.id) return;
        if (!window.confirm("Сбросить пароль в ERP? Новый пароль будет показан один раз.")) {
            return;
        }
        try {
            setResetting(true);
            const result = await resetUserPassword(initialData.id);
            const pwd = result?.password;
            if (pwd) {
                showAlert(`Новый пароль ERP: ${pwd}`, "success");
            } else {
                showAlert("Пароль сброшен", "success");
            }
        } catch (e) {
            showAlert(`Не удалось сбросить пароль: ${e.message || e}`, "error");
        } finally {
            setResetting(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        try {
            setSaving(true);
            let result;

            if (isEdit) {
                const dataToSend = {
                    role: formData.role,
                    username: formData.username.trim(),
                    full_name: formData.name,
                    department: formData.department,
                    date_hired: formData.date_hired || null,
                    user_id: initialData.user_id || null
                };
                result = await updateUser(initialData.id, dataToSend);
            } else {
                const dataToSend = {
                    username: formData.username.trim(),
                    full_name: formData.name,
                    name: formData.name,
                    role: formData.role,
                    department: formData.department,
                    date_hired: formData.date_hired || null,
                    password: formData.password.trim() || null,
                };

                result = await createUser(dataToSend);
            }

            onEmployeeAdded(result);
            if (result?.generated_password) {
                showAlert(
                    `Пользователь создан в ERP. Пароль: ${result.generated_password}`,
                    "success"
                );
            } else {
                showAlert(isEdit ? "Пользователь обновлён в ERP" : "Пользователь сохранён в ERP", "success");
            }
        } catch (e) {
            console.error("Ошибка сохранения", e);
            showAlert(`Ошибка: ${e.message}`, "error")
        } finally {
            setSaving(false);
        }
    }

    return (
        <form onSubmit={handleSubmit} className="flex flex-col h-full bg-white rounded-2xl overflow-hidden p-6" data-testid="panel-user-form">
            <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-100">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900">
                        {isEdit ? "Редактировать пользователя" : "Добавить пользователя панели"}
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">
                        {isEdit
                            ? "Изменения сохраняются в ERP и сразу видны в списке панели"
                            : "Учётка создаётся в ERP и сразу появляется в списке панели"}
                    </p>
                </div>
                <button type="button" onClick={onClose} className="w-10 h-10 flex items-center justify-center rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-700 transition-colors">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-6">
                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Основная информация</h3>
                    
                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">ФИО *</label>
                        <input
                            type="text"
                            value={formData.name}
                            onChange={(e) => handleChange('name', e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            required
                            placeholder="Иванов Иван Иванович"
                            data-testid="panel-user-name"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Роль *</label>
                            <div className="relative">
                                <select
                                    value={formData.role}
                                    onChange={(e) => handleChange('role', e.target.value)}
                                    className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                                    required
                                    data-testid="panel-user-role"
                                >
                                    {roles.map((r) => (
                                        <option key={`${r.role}-${r.name}`} value={r.role}>
                                            {r.name}{r.role && r.name !== r.role ? ` (${r.role})` : ""}
                                        </option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Отдел</label>
                            <div className="relative">
                                <select 
                                    value={formData.department || ""} 
                                    onChange={e => handleChange("department", e.target.value || null)}
                                    className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                                >
                                    <option value="">Не указан</option>
                                    {DEPARTMENTS.map(dept => (
                                        <option key={dept} value={dept}>{dept}</option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Дата выхода на работу</label>
                        <input
                            type="date"
                            value={formData.date_hired}
                            onChange={(e) => handleChange("date_hired", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            data-testid="panel-user-date-hired"
                        />
                    </div>
                </div>

                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Авторизация ERP</h3>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Email (логин) *</label>
                            <input
                                type="email"
                                value={formData.username}
                                onChange={(e) => handleChange('username', e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                required
                                placeholder="ivanov@company.com"
                                data-testid="panel-user-email"
                            />
                        </div>

                        {!isEdit ? (
                            <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                                    Пароль (пусто = сгенерирует ERP)
                                </label>
                                <input
                                    type="password"
                                    value={formData.password}
                                    onChange={(e) => handleChange('password', e.target.value)}
                                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                    placeholder="••••••••"
                                    data-testid="panel-user-password"
                                />
                            </div>
                        ) : (
                            <div className="flex flex-col justify-end">
                                <button
                                    type="button"
                                    onClick={handleResetPassword}
                                    disabled={resetting || saving}
                                    className="w-full px-4 py-2.5 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 disabled:opacity-50"
                                    data-testid="panel-user-reset-password"
                                >
                                    {resetting ? "Сброс…" : "Сбросить пароль ERP"}
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-slate-100">
                <button type="button" onClick={onClose} disabled={saving} className="px-5 py-2.5 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors">
                    Отмена
                </button>
                <button type="submit" disabled={saving} className="px-6 py-2.5 text-sm font-medium text-white bg-slate-900 rounded-xl hover:bg-slate-800 shadow-sm transition-colors flex items-center gap-2 disabled:opacity-50" data-testid="panel-user-submit">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    {saving ? "Сохранение…" : "Сохранить"}
                </button>
            </div>
        </form>
    )
}
