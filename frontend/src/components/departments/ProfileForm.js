import { useEffect, useState } from "react";
import { DEPARTMENTS } from "../../config/api";

const EMPTY = {
    department: "",
    hard_skills: "",
    experience: "",
    common_requirements: "",
};

export default function ProfileForm({
    existing,
    takenDepartments = [],
    onSubmit,
    onCancel,
    saving = false,
}) {
    const [form, setForm] = useState(EMPTY);

    useEffect(() => {
        if (existing) {
            setForm({
                department: existing.department || "",
                hard_skills: existing.hard_skills || "",
                experience: existing.expirience || existing.experience || "",
                common_requirements: existing.common_requirements || "",
            });
        } else {
            setForm(EMPTY);
        }
    }, [existing]);

    const taken = new Set(
        (takenDepartments || []).filter((d) => d && d !== existing?.department)
    );
    const departmentOptions = DEPARTMENTS.filter((d) => !taken.has(d));

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!form.department) return;
        onSubmit?.({
            department: form.department,
            hard_skills: form.hard_skills,
            experience: form.experience,
            expirience: form.experience,
            common_requirements: form.common_requirements,
        });
    };

    return (
        <form
            onSubmit={handleSubmit}
            className="mb-6 bg-white p-6 rounded-2xl shadow-sm border border-slate-200/60"
            data-testid="department-profile-form"
        >
            <h2 className="text-lg font-bold text-slate-900 mb-4">
                {existing ? "Редактировать профиль отдела" : "Новый профиль отдела"}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label className="block text-sm font-semibold text-slate-700">
                    Отдел
                    <select
                        value={form.department}
                        onChange={(e) => setForm({ ...form, department: e.target.value })}
                        className="mt-1.5 border border-slate-200 rounded-xl px-3 py-2.5 w-full bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50"
                        required
                        disabled={Boolean(existing)}
                        data-testid="department-profile-department"
                    >
                        <option value="">Выберите отдел</option>
                        {(existing?.department && !DEPARTMENTS.includes(existing.department)
                            ? [existing.department, ...departmentOptions]
                            : departmentOptions
                        ).map((dept) => (
                            <option key={dept} value={dept}>
                                {dept}
                            </option>
                        ))}
                    </select>
                </label>
                <label className="block text-sm font-semibold text-slate-700 md:col-span-2">
                    Профессиональные навыки
                    <textarea
                        value={form.hard_skills}
                        onChange={(e) => setForm({ ...form, hard_skills: e.target.value })}
                        className="mt-1.5 w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 min-h-[90px]"
                        placeholder="Например: Excel, 1С, переговоры"
                    />
                </label>
                <label className="block text-sm font-semibold text-slate-700 md:col-span-2">
                    Опыт работы
                    <textarea
                        value={form.experience}
                        onChange={(e) => setForm({ ...form, experience: e.target.value })}
                        className="mt-1.5 w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 min-h-[90px]"
                        placeholder="Например: от 2 лет в логистике"
                    />
                </label>
                <label className="block text-sm font-semibold text-slate-700 md:col-span-2">
                    Общие требования
                    <textarea
                        value={form.common_requirements}
                        onChange={(e) => setForm({ ...form, common_requirements: e.target.value })}
                        className="mt-1.5 w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 min-h-[90px]"
                        placeholder="Например: готовность к командировкам"
                    />
                </label>
            </div>
            <div className="mt-4 flex gap-2">
                <button
                    className="bg-slate-900 text-white px-5 py-2.5 rounded-xl text-sm font-medium disabled:opacity-50"
                    type="submit"
                    disabled={saving || !form.department}
                >
                    {existing ? "Сохранить" : "Создать профиль"}
                </button>
                {onCancel && (
                    <button
                        type="button"
                        className="text-slate-500 px-4 py-2.5 text-sm"
                        onClick={onCancel}
                    >
                        Отмена
                    </button>
                )}
            </div>
        </form>
    );
}
