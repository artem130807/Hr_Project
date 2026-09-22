import { useState } from "react";
import { DEPARTMENTS } from "../../config/api";

const inputClass =
    "w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all";

/**
 * Manual HR employee create (POST /employees) — not ERP panel users.
 */
export default function HiredEmployeeForm({ onClose, onSubmit, isLoading = false }) {
    const [form, setForm] = useState({
        full_name: "",
        department: DEPARTMENTS[0] || "",
        position: "",
        phone_number: "",
        date_hired: new Date().toISOString().slice(0, 10),
        gender: "",
        service_length: "0",
        adaptation_route: "",
    });
    const [error, setError] = useState("");

    const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        const fullName = form.full_name.trim();
        const position = form.position.trim();
        const department = String(form.department || "").trim();
        if (!fullName || !position || !department) {
            setError("Заполните ФИО, отдел и должность.");
            return;
        }
        const payload = {
            full_name: fullName,
            department,
            position,
            date_hired: form.date_hired || null,
            phone_number: form.phone_number.trim() || null,
            service_length: Math.max(0, Number(form.service_length) || 0),
        };
        if (form.gender === "male" || form.gender === "female") {
            payload.gender = form.gender;
        }
        if (form.adaptation_route) {
            payload.adaptation_route = form.adaptation_route;
        }
        try {
            await onSubmit(payload);
        } catch (err) {
            setError(err?.message || String(err));
        }
    };

    return (
        <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={onClose}
            data-testid="hired-employee-form-overlay"
        >
            <form
                onSubmit={handleSubmit}
                onClick={(e) => e.stopPropagation()}
                className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6"
                data-testid="hired-employee-form"
            >
                <div className="flex justify-between items-start gap-4 mb-5">
                    <div>
                        <h2 className="text-xl font-bold text-slate-900">Новый сотрудник</h2>
                        <p className="text-sm text-slate-500 mt-1">
                            Добавление в штат HR-платформы (не учётка ERP).
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-700 text-2xl leading-none"
                        aria-label="Закрыть"
                    >
                        ×
                    </button>
                </div>

                <div className="space-y-4">
                    <label className="block text-sm">
                        <span className="font-semibold text-slate-700">ФИО *</span>
                        <input
                            className={`${inputClass} mt-1.5`}
                            value={form.full_name}
                            onChange={(e) => setField("full_name", e.target.value)}
                            placeholder="Иванов Иван Иванович"
                            required
                            data-testid="employee-full-name"
                        />
                    </label>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <label className="block text-sm">
                            <span className="font-semibold text-slate-700">Отдел *</span>
                            <select
                                className={`${inputClass} mt-1.5`}
                                value={form.department}
                                onChange={(e) => setField("department", e.target.value)}
                                required
                                data-testid="employee-department"
                            >
                                {DEPARTMENTS.map((d) => (
                                    <option key={d} value={d}>
                                        {d}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <label className="block text-sm">
                            <span className="font-semibold text-slate-700">Должность *</span>
                            <input
                                className={`${inputClass} mt-1.5`}
                                value={form.position}
                                onChange={(e) => setField("position", e.target.value)}
                                placeholder="Логист"
                                required
                                data-testid="employee-position"
                            />
                        </label>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <label className="block text-sm">
                            <span className="font-semibold text-slate-700">Дата выхода на работу</span>
                            <input
                                type="date"
                                className={`${inputClass} mt-1.5`}
                                value={form.date_hired}
                                onChange={(e) => setField("date_hired", e.target.value)}
                                data-testid="employee-date-hired"
                            />
                        </label>
                        <label className="block text-sm">
                            <span className="font-semibold text-slate-700">Телефон</span>
                            <input
                                className={`${inputClass} mt-1.5`}
                                value={form.phone_number}
                                onChange={(e) => setField("phone_number", e.target.value)}
                                placeholder="+7…"
                                data-testid="employee-phone"
                            />
                        </label>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <label className="block text-sm">
                            <span className="font-semibold text-slate-700">Пол</span>
                            <select
                                className={`${inputClass} mt-1.5`}
                                value={form.gender}
                                onChange={(e) => setField("gender", e.target.value)}
                            >
                                <option value="">Не указан</option>
                                <option value="male">Мужской</option>
                                <option value="female">Женский</option>
                            </select>
                        </label>
                        <label className="block text-sm">
                            <span className="font-semibold text-slate-700">Стаж (лет)</span>
                            <input
                                type="number"
                                min={0}
                                className={`${inputClass} mt-1.5`}
                                value={form.service_length}
                                onChange={(e) => setField("service_length", e.target.value)}
                            />
                        </label>
                    </div>

                    <label className="block text-sm">
                        <span className="font-semibold text-slate-700">Маршрут адаптации</span>
                        <select
                            className={`${inputClass} mt-1.5`}
                            value={form.adaptation_route}
                            onChange={(e) => setField("adaptation_route", e.target.value)}
                            data-testid="employee-adaptation-route"
                        >
                            <option value="">Определить автоматически по должности</option>
                            <option value="full">Полная адаптация: 1 неделя, 1 месяц, 2 месяца</option>
                            <option value="control">Контроль испытательного срока: 2 месяца</option>
                        </select>
                        <span className="block mt-1 text-xs text-slate-500">
                            HR может переопределить маршрут для конкретного сотрудника.
                        </span>
                    </label>
                </div>

                {error && (
                    <p className="mt-4 text-sm text-red-600" role="alert">
                        {error}
                    </p>
                )}

                <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-100">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={isLoading}
                        className="px-4 py-2.5 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50"
                    >
                        Отмена
                    </button>
                    <button
                        type="submit"
                        disabled={isLoading}
                        className="px-5 py-2.5 text-sm font-medium text-white bg-slate-900 rounded-xl hover:bg-slate-800 disabled:opacity-50"
                        data-testid="employee-submit"
                    >
                        {isLoading ? "Сохранение…" : "Создать сотрудника"}
                    </button>
                </div>
            </form>
        </div>
    );
}
