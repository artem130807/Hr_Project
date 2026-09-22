import { useState, useEffect } from "react";
import { createCandidate, updateCandidate , getCandidatesStatuses} from "../../services/candidateApi";
import { GENDERS, WORK_EXPERIENCE, UPDATE_DATES, MARITAL_STATUS } from "../../config/api";
import { useAlertContext } from "../../context/AlertContext";
import { useAuth } from "../../context/AuthContext";
import {mapCandidateToBackend, mapCandidateFromBackend} from "../../utils/candidateMapper";
import RoleFilter from "./RoleFilter";
import { fromDateTimeLocal, toDateTimeLocal } from "../../utils/dateTimeLocal";

const MARITAL_STATUS_OPTIONS = MARITAL_STATUS;

const STAGES = ["в процессе найма", "архивирован", "в черном списке", "нанят"];


export default function CandidateForm({ initialData, onClose, onCandidateAdded }) {
    const { user } = useAuth();
    const mappedInitial = initialData ? mapCandidateFromBackend(initialData) : null;
    const initialNextContact = toDateTimeLocal(mappedInitial?.next_contact_at);
    const [statuses, setStatuses] = useState([]);

    const [formData, setFormData] = useState({
        full_name: mappedInitial?.full_name || "",
        birth_date: mappedInitial?.birth_date || "",
        phone_number: mappedInitial?.phone_number || "",
        telegram_username: mappedInitial?.telegram_username || "",
        email: mappedInitial?.email || "",
        age: mappedInitial?.age || null,
        gender: mappedInitial?.gender || GENDERS[0],
        marital_status: mappedInitial?.marital_status || MARITAL_STATUS_OPTIONS[0],
        status: mappedInitial?.status || statuses[0],
        stage: mappedInitial?.stage || "в процессе найма",
        professional_role_id: mappedInitial?.professional_role_id || null,
        hobbies: mappedInitial?.hobbies || [],
        personal_characteristics: mappedInitial?.personal_characteristics || "",
        hh_resume_link: mappedInitial?.hh_resume_link || "",
        languages: mappedInitial?.languages || [],
        relevant_position_expirience: mappedInitial?.relevant_position_expirience || "",
        certain_position_expirience: mappedInitial?.certain_position_expirience || "",
        total_work_expirience: mappedInitial?.total_work_expirience || WORK_EXPERIENCE[0],
        other_work_expirience: mappedInitial?.other_work_expirience || [],
        average_service_length: mappedInitial?.average_service_length || null,
        education: mappedInitial?.education || [],
        hard_skills: mappedInitial?.hard_skills || [],
        work_programs: mappedInitial?.work_programs || [],
        resume_update_date: mappedInitial?.resume_update_date || UPDATE_DATES[0],
        active_search: mappedInitial?.active_search !== undefined ? mappedInitial.active_search : true,
        salary_expectations: mappedInitial?.salary_expectations || null,
        next_contact_at: initialNextContact,
        next_contact_owner_id: mappedInitial?.next_contact_owner_id || null,
        next_contact_owner_name: mappedInitial?.next_contact_owner_name || null,
    });
    const { showAlert } = useAlertContext();

    useEffect(() => {
        const loadStatuses = async () => {
            try {
                const data = await getCandidatesStatuses();
                if (data && data.items && Array.isArray(data.items)) {
                    setStatuses(data.items.map(item => item.status));
                } else if (Array.isArray(data)) {
                    // если пришёл массив строк/объектов
                    setStatuses(data.map(s => (s?.status ?? s?.name ?? s?.code ?? String(s))));
                } else {
                    setStatuses([]);
                }
            } catch (e) {
                console.error("Ошибка загрузки статусов:", e);
                setStatuses([]);
            }
        };
        loadStatuses();
    }, []);

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleArrayChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const contactChanged = formData.next_contact_at !== initialNextContact;
            const preparedData = {
                ...formData,
                next_contact_at: fromDateTimeLocal(formData.next_contact_at),
                next_contact_owner_id: formData.next_contact_at
                    ? contactChanged
                        ? String(user?.erp_user_id || user?.id || "") || null
                        : formData.next_contact_owner_id
                    : null,
                next_contact_owner_name: formData.next_contact_at
                    ? contactChanged
                        ? user?.full_name || user?.name || user?.username || null
                        : formData.next_contact_owner_name
                    : null,
                hobbies: typeof formData.hobbies === "string" ? formData.hobbies.split(", ").map(s => s.trim()).filter(Boolean) : formData.hobbies,
                languages: typeof formData.languages === "string" ? formData.languages.split(", ").map(s => s.trim()).filter(Boolean) : formData.languages,
                other_work_expirience: typeof formData.other_work_expirience === "string" ? formData.other_work_expirience.split(", ").map(s => s.trim()).filter(Boolean) : formData.other_work_expirience,
                education: typeof formData.education === "string" ? formData.education.split(", ").map(s => s.trim()).filter(Boolean) : formData.education,
                hard_skills: typeof formData.hard_skills === "string" ? formData.hard_skills.split(", ").map(s => s.trim()).filter(Boolean) : formData.hard_skills,
                work_programs: typeof formData.work_programs === "string" ? formData.work_programs.split(", ").map(s => s.trim()).filter(Boolean) : formData.work_programs,
            }

            const mappedData = mapCandidateToBackend(preparedData);

            let result;
            if (initialData?.id) {
                result = await updateCandidate(initialData.id, mappedData);
            } else {
                result = await createCandidate(mappedData);
            }
            onCandidateAdded(result);
            showAlert("Кандидат сохранён","success")
        } catch (err) {
            console.error("Ошибка сохранения:", err);
            showAlert(`Ошибка: ${err.message}`, "error")
        }
    };



    return (
        <form onSubmit={handleSubmit} className="space-y-6 h-full flex flex-col p-6">
            <div className="flex justify-between items-center mb-2 pb-4 border-b border-slate-100">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900">
                        {initialData ? "Редактировать кандидата" : "Добавить кандидата"}
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">Заполните основную информацию о кандидате</p>
                </div>
                <button type="button" onClick={onClose} className="w-10 h-10 flex items-center justify-center rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-700 transition-colors">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
            </div>

            <div className="space-y-6 px-1">
                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Личная информация</h3>
                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">ФИО</label>
                        <input
                            type="text"
                            value={formData.full_name}
                            onChange={e => handleChange("full_name", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Иванов Иван Иванович"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Дата рождения</label>
                            <input
                                type="date"
                                value={formData.birth_date}
                                onChange={e => handleChange("birth_date", e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Возраст</label>
                            <input
                                type="number"
                                value={formData.age || ""}
                                onChange={e => handleChange("age", e.target.value ? parseInt(e.target.value) : null)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                min="18"
                                placeholder="Например, 30"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Телефон</label>
                            <input
                                type="tel"
                                value={formData.phone_number}
                                onChange={e => handleChange("phone_number", e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                placeholder="+79991234567"
                                maxLength="12"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Telegram</label>
                            <input
                                type="text"
                                value={formData.telegram_username}
                                onChange={e => handleChange("telegram_username", e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                placeholder="@username"
                                maxLength="64"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Почта</label>
                            <input
                                type="email"
                                value={formData.email}
                                onChange={e => handleChange("email", e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                placeholder="name@example.com"
                                maxLength="254"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Пол</label>
                            <div className="relative">
                                <select
                                    value={formData.gender}
                                    onChange={e => handleChange("gender", e.target.value)}
                                    className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                                >
                                    {GENDERS.map(gender => (
                                        <option key={gender} value={gender}>{gender}</option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Семейное положение</label>
                        <div className="relative">
                            <select
                                value={formData.marital_status}
                                onChange={e => handleChange("marital_status", e.target.value)}
                                className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                            >
                                {MARITAL_STATUS_OPTIONS.map(status => (
                                    <option key={status} value={status}>{status}</option>
                                ))}
                            </select>
                            <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Статус и профиль</h3>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Статус *</label>
                            <div className="relative">
                                <select
                                    value={formData.status}
                                    onChange={e => handleChange("status", e.target.value)}
                                    className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                                    required
                                >
                                    {statuses.map(status => (
                                        <option key={status} value={status}>{status}</option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Этап найма *</label>
                            <div className="relative">
                                <select
                                    value={formData.stage}
                                    onChange={e => handleChange("stage", e.target.value)}
                                    className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                                    required
                                >
                                    {STAGES.map(stage => (
                                        <option key={stage} value={stage}>{stage}</option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Профессиональная роль</label>
                        <div className="border border-slate-200 rounded-xl overflow-hidden bg-white">
                            <RoleFilter
                                value={formData.professional_role_id}
                                onChange={(val) => handleChange("professional_role_id", val ? Number(val) : null)}
                            />
                        </div>
                    </div>
                </div>

                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Опыт работы и образование</h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Общий опыт работы</label>
                            <div className="relative">
                                <select
                                    value={formData.total_work_expirience}
                                    onChange={e => handleChange("total_work_expirience", e.target.value)}
                                    className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                                >
                                    {WORK_EXPERIENCE.map(exp => (
                                        <option key={exp} value={exp}>{exp}</option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Средний стаж (лет)</label>
                            <input
                                type="number"
                                value={formData.average_service_length || ""}
                                onChange={e => handleChange("average_service_length", e.target.value ? parseFloat(e.target.value) : null)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                step="0.1"
                                placeholder="Например, 1.5"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Опыт на релевантной должности</label>
                        <input
                            type="text"
                            value={formData.relevant_position_expirience}
                            onChange={e => handleChange("relevant_position_expirience", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Опишите релевантный опыт..."
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Опыт на конкретной должности</label>
                        <input
                            type="text"
                            value={formData.certain_position_expirience}
                            onChange={e => handleChange("certain_position_expirience", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Опишите конкретный опыт..."
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Другой опыт работы (через запятую)</label>
                        <input
                            type="text"
                            value={Array.isArray(formData.other_work_expirience) ? formData.other_work_expirience.join(", ") : formData.other_work_expirience}
                            onChange={e => handleArrayChange("other_work_expirience", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Смежные сферы..."
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Образование (через запятую)</label>
                        <input
                            type="text"
                            value={Array.isArray(formData.education) ? formData.education.join(", ") : formData.education}
                            onChange={e => handleArrayChange("education", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="МГУ им. Ломоносова (Магистр), Курсы повышения квалификации..."
                        />
                    </div>
                </div>

                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Навыки и программы</h3>
                    
                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Hard Skills (через запятую)</label>
                        <input
                            type="text"
                            value={Array.isArray(formData.hard_skills) ? formData.hard_skills.join(", ") : formData.hard_skills}
                            onChange={e => handleArrayChange("hard_skills", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Python, SQL, Docker..."
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Языки (через запятую)</label>
                        <input
                            type="text"
                            value={Array.isArray(formData.languages) ? formData.languages.join(", ") : formData.languages}
                            onChange={e => handleArrayChange("languages", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Английский (B2), Немецкий (A1)..."
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Рабочие программы (через запятую)</label>
                        <input
                            type="text"
                            value={Array.isArray(formData.work_programs) ? formData.work_programs.join(", ") : formData.work_programs}
                            onChange={e => handleArrayChange("work_programs", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Excel, 1C, Jira..."
                        />
                    </div>
                </div>

                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Ожидания и активность</h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Ожидания по ЗП (₽)</label>
                            <input
                                type="number"
                                value={formData.salary_expectations || ""}
                                onChange={e => handleChange("salary_expectations", e.target.value ? parseInt(e.target.value) : null)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                                min="0"
                                placeholder="Например, 120000"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Дата обновления резюме</label>
                            <div className="relative">
                                <select
                                    value={formData.resume_update_date}
                                    onChange={e => handleChange("resume_update_date", e.target.value)}
                                    className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all cursor-pointer"
                                >
                                    {UPDATE_DATES.map(date => (
                                        <option key={date} value={date}>{date}</option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                </div>
                            </div>
                        </div>
                    </div>

                    <label className="flex items-center gap-3 cursor-pointer p-4 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors w-fit">
                        <input
                            type="checkbox"
                            checked={formData.active_search}
                            onChange={e => handleChange("active_search", e.target.checked)}
                            className="w-5 h-5 text-[#4f46e5] bg-white border-slate-300 rounded focus:ring-[#4f46e5] focus:ring-2 cursor-pointer"
                        />
                        <span className="text-sm font-semibold text-slate-700 select-none">В активном поиске</span>
                    </label>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                            Следующий контакт
                        </label>
                        <input
                            type="datetime-local"
                            value={formData.next_contact_at}
                            onChange={e => handleChange("next_contact_at", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50"
                        />
                        <p className="mt-1 text-xs text-slate-500">
                            Ответственным будет назначен текущий пользователь. Очистите поле, чтобы снять напоминание.
                        </p>
                    </div>
                </div>

                <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Дополнительно</h3>
                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Хобби (через запятую)</label>
                        <input
                            type="text"
                            value={Array.isArray(formData.hobbies) ? formData.hobbies.join(", ") : formData.hobbies}
                            onChange={e => handleChange("hobbies", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="Футбол, Чтение, Музыка"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Личные характеристики</label>
                        <textarea
                            value={Array.isArray(formData.personal_characteristics) ? formData.personal_characteristics.join(", ") : formData.personal_characteristics}
                            onChange={e => handleChange("personal_characteristics", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all min-h-[80px]"
                            placeholder="Ответственность, коммуникабельность..."
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">Ссылка на резюме HH</label>
                        <input
                            type="url"
                            value={formData.hh_resume_link}
                            onChange={e => handleChange("hh_resume_link", e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            placeholder="https://hh.ru/resume/..."
                        />
                    </div>
                </div>

                <div className="flex justify-end gap-3 pt-6 border-t border-slate-100">
                    <button type="button" onClick={onClose} className="px-5 py-2.5 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors">
                        Отмена
                    </button>
                    <button type="submit" className="px-6 py-2.5 text-sm font-medium text-white bg-slate-900 rounded-xl hover:bg-slate-800 shadow-sm transition-colors flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                        Сохранить
                    </button>
                </div>
            </div>
        </form>
    );
}
