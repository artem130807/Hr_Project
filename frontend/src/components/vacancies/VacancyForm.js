import { useState, useEffect } from "react";
import { createVacancy, updateVacancy, generateVacancyDescriptionAndSalary, postVacancyToHH, syncVacancyToHH, getVacancyTypes} from "../../services/vacancyApi";
import { DEPARTMENTS, GENDERS, UPDATE_DATES } from "../../config/api";
import {useAlertContext} from "../../context/AlertContext";
import {useHHDictionaries} from "../../hooks/useHHDictionaries";
import {mapVacancyToBackend, mapVacancyFromBackend} from "../../utils/vacancyMapper";
import AreaSelect from "../common/AreaSelect";
import RoleFilter from "../candidates/RoleFilter";

export default function VacancyForm({ initialData, onClose, onVacancyAdded }) {
    const {dictionaries, loading: dictLoading} =  useHHDictionaries();
    const mappedInitial = initialData ? mapVacancyFromBackend(initialData) : null;
    const [generatingFull, setGeneratingFull] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [publishAfterSave, setPublishAfterSave] = useState(false);
    const [hhUrl, setHhUrl] = useState(initialData?.hh_vacancy_url || null);
    const [vacancyTypes, setVacancyTypes] = useState([]);
    // ID вакансии: берём из initialData (редактирование) или из только что созданной (после createVacancy)
    const [editingId, setEditingId] = useState(initialData?.id ?? null);

    const [formData, setFormData] = useState({
        name: initialData?.name || "",
        vacancy_type_id: mappedInitial?.vacancy_type_id || "",
        professional_role_id: mappedInitial?.professional_role_id || null,
        description: mappedInitial?.description || "",
        synonyms: Array.isArray(mappedInitial?.synonyms) ? mappedInitial.synonyms.join(", ") : "",
        department: mappedInitial?.department || DEPARTMENTS[0],
        area_id: String(mappedInitial?.area_id ?? initialData?.area_id ?? initialData?.area?.id ?? "") || "",
        work_format: mappedInitial?.work_format || mappedInitial?.schedule_id || "",
        employment_type: mappedInitial?.employment_type || mappedInitial?.employment_id || "",
        age: mappedInitial?.age || 18,
        gender: mappedInitial?.gender || GENDERS[0],
        languages: Array.isArray(mappedInitial?.languages) ? mappedInitial.languages.join(", ") : "",
        personal_characteristics: mappedInitial?.personal_characteristics || "",
        relevant_position_expirience: mappedInitial?.relevant_position_expirience || "",
        certain_position_expirience: mappedInitial?.certain_position_expirience || "",
        total_work_expirience: mappedInitial?.total_work_expirience || "",
        other_work_expirience: Array.isArray(mappedInitial?.other_work_expirience) ? mappedInitial.other_work_expirience.join(", ") : "",
        average_service_length: mappedInitial?.average_service_length || 0,
        education: Array.isArray(mappedInitial?.education) ? mappedInitial.education.join(", ") : "",
        required_hard_skills: Array.isArray(mappedInitial?.required_hard_skills) ? mappedInitial.required_hard_skills.join(", ") : "",
        optional_hard_skills: Array.isArray(mappedInitial?.optional_hard_skills) ? mappedInitial.optional_hard_skills.join(", ") : "",
        main_tasks: Array.isArray(mappedInitial?.main_tasks) ? mappedInitial.main_tasks.join(", ") : "",
        secondary_tasks: Array.isArray(mappedInitial?.secondary_tasks) ? mappedInitial.secondary_tasks.join(", ") : "",
        work_programs: Array.isArray(mappedInitial?.work_programs) ? mappedInitial.work_programs.join(", ") : "",
        kpi_metrics: Array.isArray(mappedInitial?.kpi_metrics) ? mappedInitial.kpi_metrics.join(", ") : "",
        resume_update_date: mappedInitial?.resume_update_date || UPDATE_DATES[0],
        active_search: mappedInitial?.active_search !== undefined ? mappedInitial.active_search : true,
        work_address: mappedInitial?.work_address || "",
        is_internal_hidden: Boolean(mappedInitial?.is_internal_hidden),
        salary_from: mappedInitial?.salary_from || 0,
        salary_to: mappedInitial?.salary_to || 0,
    });
    const { showAlert } = useAlertContext();

    useEffect(() => {
        if (dictLoading) return;
        setFormData(prev => {
            const next = { ...prev };
            if (!next.work_format && dictionaries.schedules[0]?.id) {
                next.work_format = String(dictionaries.schedules[0].id);
            }
            if (!next.employment_type && dictionaries.employment[0]?.id) {
                next.employment_type = String(dictionaries.employment[0].id);
            }
            if (!next.total_work_expirience && dictionaries.experience[0]?.id) {
                next.total_work_expirience = String(dictionaries.experience[0].id);
            }
            return next;
        });
    }, [dictLoading, dictionaries]);

    useEffect(() => {
        (async () => {
            try {
                const list = await getVacancyTypes();
                const items = Array.isArray(list) ?  list : (list?.items || []);
                setVacancyTypes(items);
            } catch (e) {
                console.error("Не удалось загрузить типы вакансий", e)
                setVacancyTypes([])
            }
        })()
    }, []);

    useEffect(() => {
        if (!initialData) return;
        const incoming = mappedInitial?.area_id ?? initialData?.area_id ?? initialData?.area?.id;
        if (incoming !== undefined && incoming !== null && incoming !== "") {
            setFormData(prev => ({
                ...prev,
                area_id: String(incoming),
            }));
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialData?.id]);

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const parseArrayFields = (data) => {
        const parseString = (str) => {
            if (typeof str === 'string') {
                return str.split(',').map(s => s.trim()).filter(Boolean);
            }
            return Array.isArray(str) ? str : [];
        };

        return {
            ...data,
            synonyms: parseString(data.synonyms),
            languages: parseString(data.languages),
            other_work_expirience: parseString(data.other_work_expirience),
            education: parseString(data.education),
            required_hard_skills: parseString(data.required_hard_skills),
            optional_hard_skills: parseString(data.optional_hard_skills),
            main_tasks: parseString(data.main_tasks),
            secondary_tasks: parseString(data.secondary_tasks),
            work_programs: parseString(data.work_programs),
            kpi_metrics: parseString(data.kpi_metrics),
        };
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if ((formData.description || "").trim().length < 200) {
                showAlert("Описание вакансии должно быть не короче 200 символов (требование HH.ru)", "error");
                return;
            }
            if (!formData.professional_role_id) {
                showAlert("Укажите профессиональную роль", "error");
                return;
            }

            const parsedData = parseArrayFields(formData);
            const mappedData = mapVacancyToBackend(parsedData);
            if (mappedData.area_id !== undefined && mappedData.area_id !== null) {
                mappedData.area_id = String(mappedData.area_id);
            }

            const cleanData = {...mappedData};
            delete cleanData.id;
            delete cleanData.created_at;
            delete cleanData.updated_at;

            if (Array.isArray(cleanData.professional_roles_id)) {
                const filtered = cleanData.professional_roles_id.filter(id => id && id !== "" && id !== "0");
                if (filtered.length === 0) {
                    delete cleanData.professional_roles_id;
                } else {
                    cleanData.professional_roles_id = filtered;
                }
            }

            if(editingId) {
                Object.keys(cleanData).forEach(key => {
                    if(cleanData[key] === null || cleanData[key] === undefined || cleanData[key] === "") {
                        delete cleanData[key];
                    }
                })
            }

            let result;
            const alreadyOnHH = Boolean(
                hhUrl
                || initialData?.hh_vacancy_id
                || initialData?.hh_vacancy_url
            );
            if (editingId) {
                // PATCH on database-service auto-syncs to HH.ru when hh_vacancy_id is set
                result = await updateVacancy(editingId, cleanData);
            } else {
                result = await createVacancy(cleanData);
                if (result?.id) {
                    setEditingId(result.id);
                }
            }
            const savedId = result?.id || editingId;
            const savedArea = result?.area_id ?? result?.area?.id ?? formData.area_id;
            if (savedArea !== undefined && savedArea !== null && savedArea !== "") {
                const savedAreaStr = String(savedArea);
                setFormData(prev => ({ ...prev, area_id: savedAreaStr }));
                result = {
                    ...result,
                    area_id: savedAreaStr,
                    area: { ...(result?.area || {}), id: Number(savedAreaStr) }
                };
            }
            if (result?.hh_vacancy_url) setHhUrl(result.hh_vacancy_url);

            let finalResult = result;

            if (result?._hhSyncError) {
                showAlert(`Сохранено локально, но HH.ru не обновлён: ${result._hhSyncError}`, "warning");
            } else if (result?._hhSynced) {
                showAlert("Вакансия сохранена и обновлена на HH.ru", "success");
            } else {
                showAlert("Вакансия сохранена", "success");
            }

            if (publishAfterSave && savedId && !result?._hhSynced) {
                try {
                    setPublishing(true);
                    if (alreadyOnHH || result?.hh_vacancy_id) {
                        showAlert("Обновляем на HH.ru...", "info");
                        const synced = await syncVacancyToHH(savedId);
                        const url = synced?.alternate_url || synced?.hh_vacancy_url || hhUrl;
                        if (url) setHhUrl(url);
                        finalResult = {
                            ...result,
                            hh_vacancy_id: synced?.hh_vacancy_id ?? result?.hh_vacancy_id,
                            hh_vacancy_url: url,
                            _hhSynced: true,
                        };
                        showAlert("Вакансия обновлена на HH.ru", "success");
                    } else {
                        showAlert("Публикуем на HH.ru...", "info");
                        const published = await postVacancyToHH(savedId);
                        const url = published?.alternate_url || published?.hh_vacancy_url || null;
                        if (url) setHhUrl(url);
                        finalResult = {
                            ...result,
                            hh_vacancy_id: published?.hh_vacancy_id,
                            hh_vacancy_url: url,
                            _hhSynced: true,
                        };
                        showAlert("Вакансия опубликована на HH.ru", "success");
                    }
                } catch (pubErr) {
                    showAlert(`Сохранено локально, но публикация на HH не удалась: ${pubErr.message}`, "error");
                } finally {
                    setPublishing(false);
                }
            }

            // Close / refresh parent only after optional HH publish finishes
            onVacancyAdded(finalResult);
        } catch (err) {
            console.error("Ошибка сохранения:", err);
            showAlert(`Ошибка: ${err.message}`, "error")
        }
    };


    const validateRequiredFields = () => {
        const required = {
            "Должность": formData.name,
            "Тип вакансии": formData.vacancy_type_id,
            "Профессиональная роль": formData.professional_role_id,
            "Отдел": formData.department,
            "График работы": formData.work_format,
            "Местоположение": formData.area_id,
            "Тип занятости": formData.employment_type,
            "Возраст": formData.age,
            "Пол": formData.gender,
            "Общий опыт работы": formData.total_work_expirience,
            "Дата обновления резюме": formData.resume_update_date,
        }

        const missing = []
        for(const [field, value] of Object.entries(required)) {
            if(!value || value === "") {
                missing.push(field)
            }
        }

        return missing
    }

    const handleGenerateDescriptionAndSalary = async () => {
        const missingFields = validateRequiredFields();
        if (missingFields.length > 0) {
            showAlert(`Заполните обязательные поля: ${missingFields.join(', ')}`, "error");
            return;
        }

        try {
            setGeneratingFull(true);
            showAlert("Сохраняем вакансию...", "info");

            const parsedData = parseArrayFields(formData);
            const mappedData = mapVacancyToBackend(parsedData);
            const cleanData = { ...mappedData };
            delete cleanData.id;
            delete cleanData.created_at;
            delete cleanData.updated_at;
            delete cleanData.description;
            delete cleanData.salary_from;
            delete cleanData.salary_to;

            const savedVacancy = editingId
                ? await updateVacancy(editingId, cleanData)
                : await createVacancy(cleanData);

            const vacancyId = savedVacancy.id || editingId;
            if (savedVacancy?.id && !editingId) {
                setEditingId(savedVacancy.id);
            }

            showAlert("Генерируем описание и зарплату с помощью AI...", "info");
            const result = await generateVacancyDescriptionAndSalary(vacancyId);

            handleChange("description", result.description || "");
            if (result.salary_from !== null && result.salary_from !== undefined) {
                handleChange("salary_from", Math.round(result.salary_from));
            }
            if (result.salary_to !== null && result.salary_to !== undefined) {
                handleChange("salary_to", Math.round(result.salary_to));
            }

            // Persist AI result so publish-to-HH sees description (>=200 chars)
            const aiPatch = {
                description: result.description || "",
            };
            if (result.salary_from !== null && result.salary_from !== undefined) {
                aiPatch.salary_from = Math.round(result.salary_from);
            }
            if (result.salary_to !== null && result.salary_to !== undefined) {
                aiPatch.salary_to = Math.round(result.salary_to);
            }
            if ((aiPatch.description || "").trim().length >= 200) {
                await updateVacancy(vacancyId, aiPatch);
                showAlert("Готово! Описание сохранено, можно публиковать на HH.ru", "success");
            } else {
                showAlert("Готово! Допишите описание до 200+ символов и сохраните", "warning");
            }

        } catch (err) {
            showAlert(`Ошибка: ${err.message}`, "error");
        } finally {
            setGeneratingFull(false);
        }
    };

    const handlePublishToHH = async () => {
        try {
            setPublishing(true);

            if ((formData.description || "").trim().length < 200) {
                showAlert("Описание должно быть не короче 200 символов перед публикацией на HH.ru", "error");
                return;
            }

            showAlert("Сохраняем вакансию перед публикацией...", "info");
            const parsedData = parseArrayFields(formData);
            const mappedData = mapVacancyToBackend(parsedData);
            if (mappedData.area_id !== undefined && mappedData.area_id !== null) {
                mappedData.area_id = String(mappedData.area_id);
            }
            const cleanData = { ...mappedData };
            delete cleanData.id;
            delete cleanData.created_at;
            delete cleanData.updated_at;

            const saved = editingId
                ? await updateVacancy(editingId, cleanData)
                : await createVacancy(cleanData);
            const vacancyId = saved?.id || editingId;
            if (saved?.id) setEditingId(saved.id);
            onVacancyAdded?.(saved);

            showAlert("Публикуем на HH.ru...", "info");
            const published = await postVacancyToHH(vacancyId);
            const url = published?.alternate_url || published?.hh_vacancy_url || null;
            if (url) setHhUrl(url);
            onVacancyAdded?.({
                ...saved,
                hh_vacancy_id: published?.hh_vacancy_id,
                hh_vacancy_url: url,
            });
            showAlert(
                (hhUrl || saved?.hh_vacancy_id)
                    ? "Вакансия обновлена на HH.ru!"
                    : "Вакансия успешно опубликована на HH.ru!",
                "success"
            );
        } catch (err) {
            showAlert(`Ошибка публикации: ${err.message}`, "error");
        } finally {
            setPublishing(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">
                    {editingId ? "Редактировать вакансию" : "Создать вакансию"}
                </h2>
                <button type="button" onClick={onClose} className="text-gray-500 hover:text-gray-700">
                    ✕
                </button>
            </div>

            <div>
                <label className="block font-medium mb-1">Должность *</label>
                <input
                    type="text"
                    value={formData.name}
                    onChange={e => handleChange("name", e.target.value)}
                    className="w-full border rounded p-2"
                    required
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Профессиональные роли *</label>
                <RoleFilter
                    value={formData.professional_role_id}
                    onChange={(val) => handleChange("professional_role_id", val ? Number(val) : null)}
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Тип вакансии *</label>
                <select
                    value={String(formData.vacancy_type_id ?? "")}
                    onChange={e => handleChange("vacancy_type_id", e.target.value)} // храним строку
                    className="w-full border rounded p-2"
                >
                    <option value="">Выберите тип</option>
                    {vacancyTypes
                        .filter(t => t && t.id !== undefined && t.id !== null) // отсекаем битые
                        .map(t => (
                            <option key={t.id} value={String(t.id)}>
                                {t.name || t.title || t.label || `Тип #${t.id}`}
                            </option>
                        ))}
                </select>
            </div>

            <div>
                <label className="block font-medium mb-1">Описание вакансии (минимум 200 символов)</label>
                <textarea value={formData.description} onChange={e => handleChange("description", e.target.value)} className="w-full border rounded p-2 min-h-[120px]" required minLength="200" placeholder="Подробное описание вакансии..."/>
                <span className="text-sm text-gray-500">{formData.description.length}/200 символов</span>
            </div>

            <div>
                <label className="block font-medium mb-1">Синонимы (через запятую)</label>
                <input
                    type="text"
                    value={formData.synonyms}
                    onChange={e => handleChange("synonyms", e.target.value)}
                    className="w-full border rounded p-2"
                    placeholder="Менеджер, Специалист"
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div>
                    <label className="block font-medium mb-1">Отдел *</label>
                    <select
                        value={formData.department}
                        onChange={e => handleChange("department", e.target.value)}
                        className="w-full border rounded p-2"
                        required
                    >
                        {DEPARTMENTS.map(dept => (
                            <option key={dept} value={dept}>{dept}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block font-medium mb-1">График работы *</label>
                    <select
                        value={formData.work_format}
                        onChange={e => handleChange("work_format", e.target.value)}
                        className="w-full border rounded p-2"
                        required
                        disabled={dictLoading}
                    >
                        <option value="">Выберите график</option>
                        {dictionaries.schedules.map(item => (
                            <option key={item.id} value={item.id}>{item.name}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div>
                <label className="block font-medium mb-1">
                    Местоположение *
                </label>
                <AreaSelect
                  value={formData.area_id || ""}
                  onChange={(areaId) => {
                    if (areaId !== null && areaId !== undefined && areaId !== "" && !Number.isNaN(Number(areaId))) {
                      handleChange("area_id", String(areaId));
                    }
                  }}
                  required
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Адрес рабочего места</label>
                <input
                    type="text"
                    value={formData.work_address}
                    onChange={e => handleChange("work_address", e.target.value)}
                    className="w-full border rounded p-2"
                    placeholder="Город, улица, дом, офис"
                />
            </div>

            <div className="grid grid-cols-3 gap-4">
                <div>
                    <label className="block font-medium mb-1">Тип занятости *</label>
                    <select
                        value={formData.employment_type}
                        onChange={e => handleChange("employment_type", e.target.value)}
                        className="w-full border rounded p-2"
                        required
                        disabled={dictLoading}
                    >
                        <option value="">Выберите тип занятости</option>
                        {dictionaries.employment.map(item => (
                            <option key={item.id} value={item.id}>{item.name}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block font-medium mb-1">Возраст *</label>
                    <input
                        type="number"
                        value={formData.age}
                        onChange={e => handleChange("age", parseInt(e.target.value))}
                        className="w-full border rounded p-2"
                        required
                        min="18"
                    />
                </div>

                <div>
                    <label className="block font-medium mb-1">Пол *</label>
                    <select
                        value={formData.gender}
                        onChange={e => handleChange("gender", e.target.value)}
                        className="w-full border rounded p-2"
                        required
                    >
                        {GENDERS.map(gender => (
                            <option key={gender} value={gender}>{gender}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div>
                <label className="block font-medium mb-1">Языки (через запятую)</label>
                <input
                    type="text"
                    value={formData.languages}
                    onChange={e => handleChange("languages", e.target.value)}
                    className="w-full border rounded p-2"
                    placeholder="Русский, Английский"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Личные характеристики</label>
                <textarea
                    value={formData.personal_characteristics}
                    onChange={e => handleChange("personal_characteristics", e.target.value)}
                    className="w-full border rounded p-2 min-h-[80px]"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Опыт на релевантной должности</label>
                <input
                    type="text"
                    value={formData.relevant_position_expirience}
                    onChange={e => handleChange("relevant_position_expirience", e.target.value)}
                    className="w-full border rounded p-2"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Опыт на конкретной должности</label>
                <input
                    type="text"
                    value={formData.certain_position_expirience}
                    onChange={e => handleChange("certain_position_expirience", e.target.value)}
                    className="w-full border rounded p-2"
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div>
                    <label className="block font-medium mb-1">Общий опыт работы *</label>
                    <select
                        value={formData.total_work_expirience}
                        onChange={e => handleChange("total_work_expirience", e.target.value)}
                        className="w-full border rounded p-2"
                        required
                        disabled={dictLoading}
                    >
                        <option value="">Выберите опыт</option>
                        {dictionaries.experience.map(item => (
                            <option key={item.id} value={item.id}>{item.name}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block font-medium mb-1">Средний стаж (лет)</label>
                    <input
                        type="number"
                        value={formData.average_service_length}
                        onChange={e => handleChange("average_service_length", parseFloat(e.target.value))}
                        className="w-full border rounded p-2"
                        step="0.1"
                    />
                </div>
            </div>

            <div>
                <label className="block font-medium mb-1">Другой опыт работы (через запятую)</label>
                <input
                    type="text"
                    value={formData.other_work_expirience}
                    onChange={e => handleChange("other_work_expirience", e.target.value)}
                    className="w-full border rounded p-2"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Образование (через запятую)</label>
                <input
                    type="text"
                    value={formData.education}
                    onChange={e => handleChange("education", e.target.value)}
                    className="w-full border rounded p-2"
                    placeholder="Высшее, Среднее специальное"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Обязательные навыки (через запятую)</label>
                <input
                    type="text"
                    value={formData.required_hard_skills}
                    onChange={e => handleChange("required_hard_skills", e.target.value)}
                    className="w-full border rounded p-2"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Желательные навыки (через запятую)</label>
                <input
                    type="text"
                    value={formData.optional_hard_skills}
                    onChange={e => handleChange("optional_hard_skills", e.target.value)}
                    className="w-full border rounded p-2"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Программы для работы (через запятую)</label>
                <input
                    type="text"
                    value={formData.work_programs}
                    onChange={e => handleChange("work_programs", e.target.value)}
                    className="w-full border rounded p-2"
                    placeholder="Excel, 1C, CRM"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Основные задачи (через запятую)</label>
                <textarea
                    value={formData.main_tasks}
                    onChange={e => handleChange("main_tasks", e.target.value)}
                    className="w-full border rounded p-2 min-h-[80px]"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">Второстепенные задачи (через запятую)</label>
                <textarea
                    value={formData.secondary_tasks}
                    onChange={e => handleChange("secondary_tasks", e.target.value)}
                    className="w-full border rounded p-2 min-h-[80px]"
                />
            </div>

            <div>
                <label className="block font-medium mb-1">KPI метрики (через запятую)</label>
                <input
                    type="text"
                    value={formData.kpi_metrics}
                    onChange={e => handleChange("kpi_metrics", e.target.value)}
                    className="w-full border rounded p-2"
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div>
                    <label className="block font-medium mb-1">Зарплата от (₽)</label>
                    <input
                        type="number"
                        value={formData.salary_from}
                        onChange={e => handleChange("salary_from", parseInt(e.target.value))}
                        className="w-full border rounded p-2"
                        min="0"
                    />
                </div>

                <div>
                    <label className="block font-medium mb-1">Зарплата до (₽)</label>
                    <input
                        type="number"
                        value={formData.salary_to}
                        onChange={e => handleChange("salary_to", parseInt(e.target.value))}
                        className="w-full border rounded p-2"
                        min="0"
                    />
                </div>
            </div>

            <div>
                <label className="block font-medium mb-1">Дата обновления резюме *</label>
                <select
                    value={formData.resume_update_date}
                    onChange={e => handleChange("resume_update_date", e.target.value)}
                    className="w-full border rounded p-2"
                    required
                >
                    {UPDATE_DATES.map(date => (
                        <option key={date} value={date}>{date}</option>
                    ))}
                </select>
            </div>

            <div className="col-span-2 bg-purple-50 border-2 border-purple-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                    <div className="flex-1">
                        <h4 className="font-semibold text-purple-900 mb-1">
                            Генерация описания и зарплаты с помощью AI
                        </h4>
                        <p className="text-sm text-purple-700 mb-3">
                            Заполните все обязательные поля выше, затем нажмите кнопку.
                            AI создаст описание вакансии и предложит диапазон зарплаты на основе ваших данных.
                        </p>
                        <button type="button" onClick={handleGenerateDescriptionAndSalary} disabled={generatingFull} className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:text-gray-400 disabled:cursor-not-allowed">{generatingFull ? "Генерация..." : "Сгенерировать описание и зарплату"}</button>
                    </div>
                </div>
            </div>

            <div className="flex items-center">
                <input
                    type="checkbox"
                    checked={formData.active_search}
                    onChange={e => handleChange("active_search", e.target.checked)}
                    className="mr-2"
                    id="active_search"
                />
                <label htmlFor="active_search" className="font-medium">Активный поиск</label>
            </div>
            <div className="flex items-center gap-2">
                <input
                    type="checkbox"
                    id="is_internal_hidden"
                    checked={formData.is_internal_hidden}
                    onChange={e => handleChange("is_internal_hidden", e.target.checked)}
                />
                <label htmlFor="is_internal_hidden" className="font-medium">
                    Скрыть во внутреннем рабочем списке
                </label>
                <span className="text-sm text-gray-500">Публикация и отклики HH продолжат работать</span>
            </div>

            <div className="flex items-center">
                <input
                    type="checkbox"
                    checked={publishAfterSave}
                    onChange={e => setPublishAfterSave(e.target.checked)}
                    className="mr-2"
                    id="publish_after_save"
                />
                <label htmlFor="publish_after_save" className="font-medium">
                    {(hhUrl || initialData?.hh_vacancy_id || initialData?.hh_vacancy_url)
                        ? "После сохранения дополнительно обновить на HH.ru"
                        : "После сохранения опубликовать на HH.ru"}
                </label>
            </div>

            {hhUrl && (
                <p className="text-sm text-green-700">
                    Опубликовано на HH:{" "}
                    <a href={hhUrl} target="_blank" rel="noreferrer" className="underline">
                        {hhUrl}
                    </a>
                </p>
            )}

            <div className="flex gap-4 pt-4">
                <button
                    type="submit"
                    className="bg-slate-900 text-white px-6 py-2 rounded-xl hover:bg-slate-800 shadow-sm"
                    disabled={publishing || generatingFull}
                >
                    Сохранить
                </button>
                <button
                    type="button"
                    onClick={handlePublishToHH}
                    disabled={publishing || generatingFull}
                    className="bg-[#4f46e5] text-white px-6 py-2 rounded-xl hover:bg-[#4338ca] disabled:opacity-50 shadow-sm"
                >
                    {publishing ? "Публикация..." : (hhUrl || initialData?.hh_vacancy_id ? "Обновить на HH.ru" : "Опубликовать на HH.ru")}
                </button>
                <button
                    type="button"
                    onClick={onClose}
                    className="bg-slate-100 text-slate-700 px-6 py-2 rounded-xl hover:bg-slate-200 border border-slate-200"
                >
                    Отмена
                </button>
            </div>
        </form>
    );
}
