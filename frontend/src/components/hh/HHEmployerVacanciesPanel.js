import { useEffect, useMemo, useState } from "react";
import {
    getHHEmployerVacancies,
    linkHHVacancyToLocal,
    importHHVacancyToLocal,
} from "../../services/hhImportApi";
import { DEPARTMENTS } from "../../config/api";
import { useAlertContext } from "../../context/AlertContext";
import HHNegotiationsModal from "./HHNegotiationsModal";

const hhKey = (id) => String(id ?? "");

export default function HHEmployerVacanciesPanel({
    localVacancies = [],
    onLinked,
    defaultDepartment,
}) {
    const { showAlert } = useAlertContext();
    const [archived, setArchived] = useState(false);
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(false);
    const [page, setPage] = useState(0);
    const [pages, setPages] = useState(0);
    const [found, setFound] = useState(0);
    const [warning, setWarning] = useState(null);
    const [linking, setLinking] = useState({});
    const [negotiationsFor, setNegotiationsFor] = useState(null);
    const [linkSelect, setLinkSelect] = useState({});
    const [department, setDepartment] = useState(
        () => defaultDepartment || DEPARTMENTS[0] || "логистический"
    );

    useEffect(() => {
        if (defaultDepartment) setDepartment(defaultDepartment);
    }, [defaultDepartment]);

    const localOptions = useMemo(() => {
        const list = Array.isArray(localVacancies) ? localVacancies : [];
        const unbound = [];
        const bound = [];
        for (const lv of list) {
            if (lv?.is_template) continue;
            if (lv?.hh_vacancy_id || lv?.hh_vacancy_url) bound.push(lv);
            else unbound.push(lv);
        }
        return { unbound, bound, all: [...unbound, ...bound] };
    }, [localVacancies]);

    const load = async (arch = archived, pageNum = 0) => {
        try {
            setLoading(true);
            const data = await getHHEmployerVacancies({
                archived: arch,
                page: pageNum,
                per_page: 50,
                all_accessible: true,
            });
            setItems(data?.items || []);
            setPages(data?.pages || 0);
            setFound(data?.found || 0);
            setPage(data?.page ?? pageNum);
            setWarning(data?.warning || null);
        } catch (e) {
            showAlert(`Не удалось загрузить вакансии HH: ${e.message || e}`, "error");
            setItems([]);
            setWarning(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load(false, 0);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const handleLink = async (hhId) => {
        const key = hhKey(hhId);
        const localId = Number(linkSelect[key]);
        const hasLocal = Number.isFinite(localId) && localId > 0;

        try {
            setLinking((prev) => ({ ...prev, [key]: true }));
            if (hasLocal) {
                await linkHHVacancyToLocal(hhId, localId);
                showAlert("Вакансия привязана к HH", "success");
            } else {
                if (!department) {
                    showAlert("Выберите отдел для импорта вакансии", "warning");
                    return;
                }
                const result = await importHHVacancyToLocal(hhId, department);
                if (result?.created === false || result?.status === "already_linked") {
                    showAlert(
                        `Уже привязана к локальной #${result.local_vacancy_id}`,
                        "info"
                    );
                } else {
                    showAlert(
                        `Вакансия создана в платформе (#${result?.local_vacancy_id}) и привязана к HH`,
                        "success"
                    );
                }
            }
            setLinkSelect((prev) => {
                const next = { ...prev };
                delete next[key];
                return next;
            });
            await load(archived, page);
            onLinked?.();
        } catch (e) {
            showAlert(
                hasLocal
                    ? `Привязка не удалась: ${e.message || e}`
                    : `Импорт не удался: ${e.message || e}`,
                "error"
            );
        } finally {
            setLinking((prev) => ({ ...prev, [key]: false }));
        }
    };

    return (
        <div>
            <div className="flex flex-wrap gap-4 items-center mb-6 bg-white p-4 rounded-2xl shadow-sm border border-slate-200/60">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700 cursor-pointer select-none">
                    <div className="relative flex items-center">
                        <input
                            type="checkbox"
                            checked={archived}
                            className="sr-only peer"
                            onChange={(e) => {
                                const next = e.target.checked;
                                setArchived(next);
                                load(next, 0);
                            }}
                        />
                        <div className="w-10 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#4f46e5]"></div>
                    </div>
                    Архивные
                </label>

                <div className="h-6 w-px bg-slate-200 hidden sm:block"></div>

                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                    <span className="text-slate-500 whitespace-nowrap">Отдел при импорте</span>
                    <select
                        className="border border-slate-200 rounded-xl text-sm px-3 py-1.5 bg-white focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] outline-none"
                        value={department}
                        onChange={(e) => setDepartment(e.target.value)}
                    >
                        {DEPARTMENTS.map((d) => (
                            <option key={d} value={d}>
                                {d}
                            </option>
                        ))}
                    </select>
                </label>

                <span className="text-sm font-medium text-slate-500">
                    Найдено на HH: <span className="text-slate-900">{found}</span>
                </span>

                <button
                    type="button"
                    onClick={() => load(archived, page)}
                    className="ml-auto text-sm px-4 py-2 bg-slate-50 text-slate-700 font-medium rounded-xl border border-slate-200 hover:bg-slate-100 transition-colors flex items-center gap-2"
                >
                    <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                    Обновить
                </button>
            </div>

            <div className="mb-6 text-sm text-slate-600 bg-slate-50 border border-slate-100 rounded-2xl px-4 py-3">
                Без выбора локальной карточки кнопка создаст вакансию в платформе из данных HH
                (название, город, зарплата, роли) в выбранном отделе и сразу привяжет её.
                Если карточка уже есть — выберите её в списке и нажмите «Привязать».
            </div>

            {warning && (
                <div className="mb-6 text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-2xl px-4 py-3">
                    {warning}
                </div>
            )}
            {loading ? (
                <div className="flex justify-center items-center py-12 text-slate-400">
                    <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Загрузка...
                </div>
            ) : items.length === 0 ? (
                <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <p className="text-slate-500 font-medium">В этом списке нет вакансий с HH.ru</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                    {items.map((v) => {
                        const key = hhKey(v.hh_vacancy_id);
                        const selected = linkSelect[key] || "";
                        const isLinking = Boolean(linking[key]);
                        const canPickLocal = localOptions.all.length > 0;
                        const willImport = !selected;

                        return (
                        <div key={key} className="bg-white rounded-2xl shadow-sm border border-slate-200/60 hover:shadow-md transition-shadow flex flex-col">
                            <div className="p-6 flex-1">
                                <div className="flex justify-between items-start mb-2 gap-2">
                                    <span className="text-[10px] font-bold tracking-wider text-slate-400 uppercase bg-slate-50 px-2 py-0.5 rounded border border-slate-100">HH-{v.hh_vacancy_id}</span>
                                    <div className="flex flex-wrap gap-1 justify-end">
                                        {v.closed_for_applicants && (
                                            <span className="text-[10px] font-bold tracking-wider text-rose-700 uppercase bg-rose-50 px-2 py-0.5 rounded border border-rose-100">
                                                Скрыта из поиска
                                            </span>
                                        )}
                                        {v.local_vacancy_id ? (
                                            <span className="text-[10px] font-bold tracking-wider text-green-700 uppercase bg-green-50 px-2 py-0.5 rounded border border-green-100 flex items-center gap-1">
                                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                                Привязана #{v.local_vacancy_id}
                                            </span>
                                        ) : (
                                            <span className="text-[10px] font-bold tracking-wider text-amber-700 uppercase bg-amber-50 px-2 py-0.5 rounded border border-amber-100 flex items-center gap-1">
                                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                                Не привязана
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <h3 className="font-bold text-lg mb-3 text-slate-900 leading-tight">{v.name}</h3>

                                <div className="space-y-2 text-sm text-slate-600 mb-4">
                                    {v.area && (
                                        <div className="flex items-center gap-2">
                                            <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                            <span className="truncate">{v.area}</span>
                                        </div>
                                    )}
                                    {(v.salary_from || v.salary_to) && (
                                        <div className="flex items-center gap-2 font-medium text-slate-900">
                                            <svg className="w-4 h-4 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                            <span>
                                                {[v.salary_from, v.salary_to].filter(Boolean).join(" – ")}{" "}
                                                {v.currency || "RUR"}
                                            </span>
                                        </div>
                                    )}
                                    {v.published_at && (
                                        <div className="flex items-center gap-2 text-slate-400">
                                            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                                            <span>{new Date(v.published_at).toLocaleDateString("ru-RU")}</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="p-4 border-t border-slate-100 bg-slate-50/50 rounded-b-2xl flex flex-col gap-3">
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setNegotiationsFor({ id: v.hh_vacancy_id, name: v.name })}
                                        className="flex-1 bg-indigo-600 text-white text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-indigo-700 transition-colors shadow-sm flex justify-center items-center gap-2"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" /></svg>
                                        Отклики
                                    </button>
                                    {v.alternate_url && (
                                        <a
                                            href={v.alternate_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="w-12 shrink-0 bg-white border border-slate-200 text-slate-500 hover:text-slate-800 rounded-xl hover:bg-slate-50 flex items-center justify-center transition-colors shadow-sm"
                                            title="Открыть на HH"
                                        >
                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                                        </a>
                                    )}
                                </div>
                                {!v.local_vacancy_id && (
                                    <div className="flex flex-col gap-2">
                                        <div className="flex gap-2">
                                            <select
                                                className="flex-1 min-w-0 border border-slate-200 rounded-xl text-sm px-3 py-2 bg-white focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] outline-none disabled:opacity-60"
                                                value={selected}
                                                disabled={!canPickLocal || isLinking}
                                                onChange={(e) =>
                                                    setLinkSelect((prev) => ({
                                                        ...prev,
                                                        [key]: e.target.value,
                                                    }))
                                                }
                                            >
                                                <option value="">
                                                    {canPickLocal
                                                        ? "Или выбрать существующую…"
                                                        : "Создать новую из HH"}
                                                </option>
                                                {localOptions.unbound.map((lv) => (
                                                    <option key={lv.id} value={String(lv.id)}>
                                                        {lv.public_code || `В-${lv.id}`} · {lv.name}
                                                    </option>
                                                ))}
                                                {localOptions.bound.length > 0 && (
                                                    <optgroup label="Уже связаны с HH (перепривязка)">
                                                        {localOptions.bound.map((lv) => (
                                                            <option key={lv.id} value={String(lv.id)}>
                                                                {lv.public_code || `В-${lv.id}`} · {lv.name}
                                                            </option>
                                                        ))}
                                                    </optgroup>
                                                )}
                                            </select>
                                            <button
                                                type="button"
                                                disabled={isLinking}
                                                title={
                                                    willImport
                                                        ? `Создать в платформе (отдел: ${department}) и привязать`
                                                        : "Привязать к выбранной локальной вакансии"
                                                }
                                                onClick={() => handleLink(v.hh_vacancy_id)}
                                                className="shrink-0 text-sm bg-slate-800 text-white px-4 py-2 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-700 transition-colors font-medium shadow-sm"
                                            >
                                                {isLinking
                                                    ? "..."
                                                    : willImport
                                                      ? "Импортировать"
                                                      : "Привязать"}
                                            </button>
                                        </div>
                                        <p className="text-xs text-slate-500">
                                            {willImport
                                                ? `«Импортировать» создаст карточку в отделе «${department}» и свяжет с HH.`
                                                : "«Привязать» свяжет выбранную локальную вакансию с этой HH."}
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                        );
                    })}
                </div>
            )}

            {pages > 1 && (
                <div className="flex justify-between items-center mt-8 p-4 bg-white rounded-2xl shadow-sm border border-slate-200/60">
                    <button
                        type="button"
                        disabled={page <= 0 || loading}
                        onClick={() => load(archived, page - 1)}
                        className="text-sm px-4 py-2 border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 font-medium text-slate-700 transition-colors"
                    >
                        Назад
                    </button>
                    <span className="text-sm font-medium text-slate-500">
                        Страница <span className="text-slate-900">{page + 1}</span> из <span className="text-slate-900">{pages}</span>
                    </span>
                    <button
                        type="button"
                        disabled={page + 1 >= pages || loading}
                        onClick={() => load(archived, page + 1)}
                        className="text-sm px-4 py-2 border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 font-medium text-slate-700 transition-colors"
                    >
                        Вперёд
                    </button>
                </div>
            )}

            {negotiationsFor && (
                <HHNegotiationsModal
                    hhVacancyId={negotiationsFor.id}
                    vacancyName={negotiationsFor.name}
                    onClose={() => setNegotiationsFor(null)}
                />
            )}
        </div>
    );
}
