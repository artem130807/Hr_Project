import {useState} from "react";
import {postVacancyToHH, syncVacancyToHH} from "../../services/vacancyApi";
import {runVacancyFilterNow, formatFilterRunSummary} from "../../services/vacancyFilterApi";
import {useAlertContext} from "../../context/AlertContext";
import VacancyTestsManager from "./VacancyTestsManager";
import {useHHDictionaries} from "../../hooks/useHHDictionaries";
import {
    scheduleLabel,
    employmentLabel,
} from "../../utils/hhLabels";

export default function VacancyList({
    vacancies,
    onVacancyDeleted,
    onVacancyEdit,
    onVacancyUpdated,
    onOpenHHNegotiations,
    onManageFilter,
}) {
    const {showAlert} = useAlertContext();
    const {dictionaries} = useHHDictionaries();
    const [publishing, setPublishing] = useState({});
    const [syncing, setSyncing] = useState({});
    const [managingTest, setManagementTests] = useState(null);
    const [templating, setTemplating] = useState({});
    const [runningFilter, setRunningFilter] = useState({});

    const handleRunFilter = async (vacancy) => {
        const id = Number(vacancy?.id);
        if (!Number.isFinite(id)) return;
        if (!vacancy?.filter_id) {
            showAlert("Сначала привяжите фильтр к вакансии", "warning");
            return;
        }
        if (!vacancy?.hh_vacancy_id && !vacancy?.hh_vacancy_url) {
            showAlert("Сначала опубликуйте или привяжите вакансию к HH.ru", "warning");
            return;
        }
        try {
            setRunningFilter((prev) => ({ ...prev, [id]: true }));
            showAlert("Прогоняем фильтр по откликам HH (порция отказов)…", "info");
            const result = await runVacancyFilterNow(id);
            const { msg, level } = formatFilterRunSummary(result?.summary || result || {});
            showAlert(msg, level);
        } catch (e) {
            showAlert(`Не удалось прогнать фильтр: ${e.message || e}`, "error");
        } finally {
            setRunningFilter((prev) => ({ ...prev, [id]: false }));
        }
    };

    const handlePublishToHH = async (vacancy) => {
        const id = Number(vacancy?.id);

        if (!Number.isFinite(id)) {
            showAlert("Некорректный vacancy.id — не могу опубликовать", "error");
            return;
        }

        try {
            setPublishing(prev => ({ ...prev, [id]: true }));
            showAlert("Публикуем вакансию...", "info");

            const published = await postVacancyToHH(id, {});
            const updated = {
                ...vacancy,
                hh_vacancy_id: published?.hh_vacancy_id ?? vacancy.hh_vacancy_id,
                hh_vacancy_url: published?.alternate_url ?? published?.hh_vacancy_url ?? vacancy.hh_vacancy_url,
            };
            onVacancyUpdated?.(updated);
            showAlert("Вакансия успешно опубликована на HH.ru!", "success");
        } catch (err) {
            const msg = err?.message || "Неизвестная ошибка";
            showAlert(`Ошибка публикации: ${msg}`, "error");
            console.error("HH publish error:", err);
        } finally {
            setPublishing(prev => ({ ...prev, [id]: false }));
        }
    };

    const handleSyncToHH = async (vacancy) => {
        const id = Number(vacancy?.id);
        if (!Number.isFinite(id)) {
            showAlert("Некорректный vacancy.id — не могу обновить на HH", "error");
            return;
        }
        try {
            setSyncing((prev) => ({ ...prev, [id]: true }));
            showAlert("Обновляем вакансию на HH.ru...", "info");
            const synced = await syncVacancyToHH(id);
            onVacancyUpdated?.({
                ...vacancy,
                hh_vacancy_id: synced?.hh_vacancy_id ?? vacancy.hh_vacancy_id,
                hh_vacancy_url:
                    synced?.alternate_url ?? synced?.hh_vacancy_url ?? vacancy.hh_vacancy_url,
            });
            showAlert("Вакансия обновлена на HH.ru", "success");
        } catch (err) {
            showAlert(`Не удалось обновить на HH.ru: ${err?.message || err}`, "error");
            console.error("HH sync error:", err);
        } finally {
            setSyncing((prev) => ({ ...prev, [id]: false }));
        }
    };

    const handleMakeTemplate = async (vacancy) => {
        const id = Number(vacancy?.id);
        if (!Number.isFinite(id)) return;
        try {
            setTemplating((prev) => ({ ...prev, [id]: true }));
            const { makeVacancyTemplate } = await import("../../services/vacancyApi");
            const cloned = await makeVacancyTemplate(id);
            onVacancyUpdated?.(cloned);
            showAlert(`Шаблон создан: ${cloned.public_code || cloned.name}`, "success");
        } catch (err) {
            showAlert(`Не удалось создать шаблон: ${err.message || err}`, "error");
        } finally {
            setTemplating((prev) => ({ ...prev, [id]: false }));
        }
    };

    if(!vacancies || vacancies.length === 0) {
        return (
            <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                </div>
                <h3 className="text-lg font-medium text-slate-800">Нет вакансий</h3>
                <p className="text-slate-500 mt-1">Добавьте новую вакансию, чтобы начать работу.</p>
            </div>
        );
    }

    const cardTone = (vacancy) => {
        if (vacancy.deadline_state === "overdue") return "bg-red-50/50 border-red-200";
        if (vacancy.deadline_state === "warning") return "bg-yellow-50/50 border-yellow-200";
        if (vacancy.is_template) return "bg-slate-50/50 border-slate-200 border-dashed";
        return "bg-white border-slate-200/60";
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {vacancies.map(vacancy => {
                const scheduleId = vacancy.schedule_id || vacancy.work_format;
                const employmentId = vacancy.employment_id || vacancy.employment_type;
                const scheduleText = scheduleLabel(scheduleId, dictionaries);
                const employmentText = employmentLabel(employmentId, dictionaries);

                return (
                <div key={vacancy.id} className={`${cardTone(vacancy)} rounded-2xl shadow-sm border hover:shadow-md transition-all duration-300 flex flex-col`}>
                    <div className="p-6 flex-1">
                        <div className="flex justify-between items-start mb-4">
                            <div className="flex-1 pr-4">
                                <div className="flex items-center gap-2 mb-1.5">
                                    <span className="text-xs font-semibold text-slate-400 tracking-wide uppercase">
                                        {vacancy.public_code || `В-${vacancy.id}`}
                                    </span>
                                    {vacancy.is_template && (
                                        <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-medium tracking-wide uppercase border border-slate-200">
                                            Шаблон
                                        </span>
                                    )}
                                    {vacancy.is_internal_hidden && (
                                        <span className="ml-2 px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-bold uppercase">
                                            Скрыта внутри
                                        </span>
                                    )}
                                    {vacancy.filter_id ? (
                                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-medium tracking-wide uppercase border border-blue-100">
                                            Фильтр #{vacancy.filter_id}
                                        </span>
                                    ) : null}
                                    {vacancy.deadline_state === "overdue" && (
                                        <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-[10px] font-bold tracking-wide uppercase border border-red-200">
                                            Просрочено
                                        </span>
                                    )}
                                </div>
                                <h3 className="text-lg font-bold text-slate-900 leading-tight">{vacancy.name}</h3>
                            </div>
                            <span className="shrink-0 px-2.5 py-1 bg-yellow-50 text-yellow-800 border border-yellow-100 rounded-lg text-xs font-medium">
                                {vacancy.department || "Без отдела"}
                            </span>
                        </div>

                        {vacancy.work_address ? (
                            <p className="mb-3 text-xs text-slate-500">Адрес: {vacancy.work_address}</p>
                        ) : null}

                        <div className="space-y-2.5 text-sm mb-5 text-slate-600">
                            {(vacancy.city || vacancy.region) && (
                                <div className="flex items-center gap-2">
                                    <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                    <span className="truncate">
                                        {[vacancy.city, vacancy.region].filter(Boolean).join(", ")}
                                    </span>
                                </div>
                            )}

                            {(scheduleText || employmentText) && (
                                <div className="flex items-center gap-2">
                                    <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    <span className="truncate">{[scheduleText, employmentText].filter(Boolean).join(" · ")}</span>
                                </div>
                            )}

                            {(vacancy.salary_from > 0 || vacancy.salary_to > 0) && (
                                <div className="flex items-center gap-2 font-medium text-slate-900">
                                    <svg className="w-4 h-4 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    <span>
                                        {vacancy.salary_from > 0 && vacancy.salary_from.toLocaleString("ru-RU")}
                                        {vacancy.salary_from > 0 && vacancy.salary_to > 0 && " – "}
                                        {vacancy.salary_to > 0 && vacancy.salary_to.toLocaleString("ru-RU")}
                                        {" ₽"}
                                    </span>
                                </div>
                            )}
                        </div>

                        {Array.isArray(vacancy.required_hard_skills) && vacancy.required_hard_skills.length > 0 && (
                            <div className="mb-4">
                                <div className="flex flex-wrap gap-1.5">
                                    {vacancy.required_hard_skills.slice(0, 4).map((skill, idx) => (
                                        <span key={idx} className="px-2 py-1 bg-slate-100 text-slate-600 rounded border border-slate-200/60 text-xs font-medium">{skill}</span>
                                    ))}
                                    {vacancy.required_hard_skills.length > 4 && (
                                        <span className="px-2 py-1 bg-slate-50 text-slate-500 rounded border border-slate-200/60 text-xs font-medium">
                                            +{vacancy.required_hard_skills.length - 4}
                                        </span>
                                    )}
                                </div>
                            </div>
                        )}
                        
                        <div className="flex gap-2 flex-wrap">
                            <button
                                type="button"
                                onClick={() => setManagementTests(vacancy.id)}
                                className="text-sm px-3 py-1.5 bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg transition-colors font-medium border border-transparent hover:border-slate-300"
                                title="Привязать тесты к вакансии"
                            >
                                Тесты
                            </button>
                            {onManageFilter && (
                                <button
                                    type="button"
                                    data-testid={`vacancy-filter-btn-${vacancy.id}`}
                                    onClick={() => onManageFilter(vacancy)}
                                    className="text-sm px-3 py-1.5 bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg transition-colors font-medium border border-transparent hover:border-slate-300"
                                >
                                    {vacancy.filter_id ? "Фильтр" : "Добавить фильтр"}
                                </button>
                            )}
                            {vacancy.filter_id && (vacancy.hh_vacancy_id || vacancy.hh_vacancy_url) ? (
                                <button
                                    type="button"
                                    data-testid={`vacancy-run-filter-${vacancy.id}`}
                                    onClick={() => handleRunFilter(vacancy)}
                                    disabled={Boolean(runningFilter[vacancy.id])}
                                    title="Отказать порцией откликов на HH, которые не проходят фильтр (лимит, чтобы не нагружать API)"
                                    className="text-sm px-3 py-1.5 bg-[#4f46e5]/15 text-slate-800 hover:bg-[#4f46e5]/25 rounded-lg transition-colors font-medium border border-[#4f46e5]/40 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {runningFilter[vacancy.id] ? "Прогон…" : "Прогнать фильтр"}
                                </button>
                            ) : null}
                            <button 
                                onClick={() => handleMakeTemplate(vacancy)}
                                disabled={templating[vacancy.id] || vacancy.is_template}
                                className="text-sm px-3 py-1.5 bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg transition-colors font-medium border border-transparent hover:border-slate-300 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {templating[vacancy.id] ? "..." : "В шаблон"}
                            </button>
                        </div>
                    </div>

                    <div className="p-4 border-t border-slate-100 bg-slate-50/50 rounded-b-2xl">
                        <div className="flex gap-2 items-center">
                            <button
                                type="button"
                                onClick={() => onVacancyEdit(vacancy)}
                                className="flex-1 bg-white border border-slate-200 text-slate-700 px-3 py-2 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition-colors text-sm font-medium shadow-sm"
                            >
                                Изменить
                            </button>

                            {(vacancy.hh_vacancy_id || vacancy.hh_vacancy_url) ? (
                                <>
                                    <button
                                        type="button"
                                        onClick={() => handleSyncToHH(vacancy)}
                                        disabled={syncing[vacancy.id]}
                                        className="flex-1 bg-indigo-600 text-white px-3 py-2 rounded-xl hover:bg-indigo-700 transition-colors text-sm font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {syncing[vacancy.id] ? "Обновляем..." : "Обновить на HH"}
                                    </button>
                                    <a
                                        href={vacancy.hh_vacancy_url || `https://hh.ru/vacancy/${vacancy.hh_vacancy_id}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="w-10 shrink-0 bg-green-50 border border-green-200 text-green-700 px-0 py-2 rounded-xl hover:bg-green-100 transition-colors text-sm font-medium shadow-sm flex items-center justify-center"
                                        title="Открыть на HH.ru"
                                    >
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                                    </a>
                                </>
                            ) : (
                                <button
                                    type="button"
                                    onClick={() => handlePublishToHH(vacancy)}
                                    disabled={publishing[vacancy.id]}
                                    className="flex-1 bg-indigo-600 text-white px-3 py-2 rounded-xl hover:bg-indigo-700 transition-colors text-sm font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {publishing[vacancy.id] ? "Публикуем..." : "На HH.ru"}
                                </button>
                            )}

                            {(() => {
                                const hhId = vacancy.hh_vacancy_id || (String(vacancy.hh_vacancy_url || "").match(/\/vacancy\/(\d+)/) || [])[1];
                                if (!hhId || !onOpenHHNegotiations) return null;
                                return (
                                    <button
                                        type="button"
                                        onClick={() => onOpenHHNegotiations({ ...vacancy, hh_vacancy_id: String(hhId) })}
                                        className="w-10 shrink-0 bg-white border border-yellow-300 text-yellow-700 px-0 py-2 rounded-xl hover:bg-yellow-50 transition-colors text-sm font-medium shadow-sm flex items-center justify-center"
                                        title="Отклики"
                                    >
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" /></svg>
                                    </button>
                                );
                            })()}

                            <button
                                type="button"
                                onClick={() => onVacancyDeleted(vacancy)}
                                className="w-10 shrink-0 bg-white border border-red-200 text-red-500 px-0 py-2 rounded-xl hover:bg-red-50 hover:border-red-300 transition-colors text-sm font-medium shadow-sm flex items-center justify-center"
                                title="Удалить"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                            </button>
                        </div>
                    </div>
                </div>
                )
            })}

            {managingTest && (
                <VacancyTestsManager
                    vacancyId={managingTest}
                    vacancyName={
                        vacancies.find((v) => v.id === managingTest)?.name
                    }
                    onClose={() => setManagementTests(null)}
                />
            )}
        </div>
    );
}
