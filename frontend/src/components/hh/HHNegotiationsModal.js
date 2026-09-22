import { useEffect, useState } from "react";
import {
    getHHVacancyNegotiations,
    importHHNegotiation,
    getHHNegotiationDetail,
    executeHHNegotiationAction,
} from "../../services/hhImportApi";
import {
    actionButtonVariant,
    actionNeedsMessage,
    enabledActions,
    hhActionLabel,
} from "../../utils/hhNegotiationActions";
import { formatHhFullName } from "../../utils/candidateMapper";
import { formatExperienceMonths, mapHhResumeToProfile } from "../../utils/hhNegotiationResume";
import {
    EMPTY_NEGOTIATION_FILTERS,
    filterNegotiationItems,
    hasNegotiationFilters,
} from "../../utils/negotiationListFilters";
import { useAlertContext } from "../../context/AlertContext";
import NegotiationResumeModal from "./NegotiationResumeModal";
import HHNegotiationsFilters from "./HHNegotiationsFilters";

const ACTION_BTN_CLASS = {
    danger: "bg-red-50 text-red-700 border-red-200 hover:bg-red-100",
    success: "bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100",
    primary: "bg-slate-50 text-slate-800 border-slate-200 hover:bg-slate-100",
};

export default function HHNegotiationsModal({ hhVacancyId, vacancyName, onClose }) {
    const { showAlert } = useAlertContext();
    const [collection, setCollection] = useState("response");
    const [collections, setCollections] = useState([]);
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(false);
    const [importing, setImporting] = useState({});
    const [page, setPage] = useState(0);
    const [pages, setPages] = useState(0);
    const [found, setFound] = useState(0);
    const [onlyUnviewed, setOnlyUnviewed] = useState(false);
    const [listFilters, setListFilters] = useState(EMPTY_NEGOTIATION_FILTERS);
    const [bulkImporting, setBulkImporting] = useState(false);
    const [importedIds, setImportedIds] = useState({});

    const [selectedId, setSelectedId] = useState(null);
    const [detail, setDetail] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [actionBusy, setActionBusy] = useState(null);
    const [actionMessage, setActionMessage] = useState("");
    const [pendingActionId, setPendingActionId] = useState(null);
    const [resumeCardOpen, setResumeCardOpen] = useState(false);

    const load = async (coll = collection, pageNum = 0) => {
        if (!hhVacancyId) return;
        try {
            setLoading(true);
            let data = await getHHVacancyNegotiations(hhVacancyId, {
                collection: coll,
                page: pageNum,
                per_page: 50,
            });
            const cols = data?.collections || [];
            if (
                cols.length &&
                data?.collection &&
                data.collection !== coll &&
                !cols.some((c) => c.id === coll)
            ) {
                setCollection(data.collection);
            } else if (data?.warning && cols.length && cols[0]?.id && cols[0].id !== coll) {
                const fallback = cols[0].id;
                setCollection(fallback);
                data = await getHHVacancyNegotiations(hhVacancyId, {
                    collection: fallback,
                    page: 0,
                    per_page: 50,
                });
            }
            setItems(data?.items || []);
            setCollections(data?.collections || cols);
            setPages(data?.pages || 0);
            setFound(data?.found || 0);
            setPage(data?.page ?? pageNum);
            if (data?.collection) setCollection(data.collection);
            if (data?.warning) {
                showAlert(data.warning, "warning");
            }
        } catch (e) {
            showAlert(`Не удалось загрузить отклики: ${e.message || e}`, "error");
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    const loadDetail = async (negotiationId) => {
        if (!negotiationId) return;
        try {
            setDetailLoading(true);
            const data = await getHHNegotiationDetail(negotiationId);
            setDetail(data);
            setActionMessage("");
            setPendingActionId(null);
        } catch (e) {
            showAlert(`Не удалось загрузить отклик: ${e.message || e}`, "error");
            setDetail(null);
        } finally {
            setDetailLoading(false);
        }
    };

    useEffect(() => {
        load("response", 0);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hhVacancyId]);

    const handleSelect = (item) => {
        const id = item?.id;
        if (!id) return;
        setSelectedId(id);
        setResumeCardOpen(false);
        loadDetail(id);
    };

    const isAlreadyCandidate = (item) => {
        if (!item?.id) return false;
        if (importedIds[item.id] || item.already_candidate) return true;
        const row = items.find((entry) => entry.id === item.id);
        return Boolean(row?.already_candidate);
    };

    const handleImport = async (item) => {
        const id = item?.id;
        if (!id) return;
        if (isAlreadyCandidate(item)) {
            showAlert("Этот человек уже в кандидатах", "warning");
            return;
        }
        try {
            setImporting((prev) => ({ ...prev, [id]: true }));
            const res = await importHHNegotiation(hhVacancyId, id, { collection });
            setImportedIds((prev) => ({ ...prev, [id]: true }));
            setItems((prev) =>
                prev.map((row) =>
                    row.id === id
                        ? { ...row, already_candidate: true, candidate_id: res?.candidate_id || row.candidate_id }
                        : row
                )
            );
            if (detail?.id === id) {
                setDetail((prev) =>
                    prev ? { ...prev, already_candidate: true, candidate_id: res?.candidate_id || prev.candidate_id } : prev
                );
            }
            if (res?.status === "already_exists" || res?.created === false) {
                showAlert("Этот человек уже в кандидатах", "warning");
            } else {
                showAlert(`Кандидат #${res.candidate_id} импортирован`, "success");
            }
        } catch (e) {
            showAlert(`Импорт не удался: ${e.message || e}`, "error");
        } finally {
            setImporting((prev) => ({ ...prev, [id]: false }));
        }
    };

    const runAction = async (actionId, argumentsPayload) => {
        if (!selectedId || !actionId) return;
        try {
            setActionBusy(actionId);
            const res = await executeHHNegotiationAction(selectedId, actionId, {
                arguments: argumentsPayload,
            });
            const label = hhActionLabel({ id: actionId, name: actionId });
            showAlert(`Действие «${label}» выполнено на HH.ru`, "success");
            if (res?.negotiation) {
                setDetail(res.negotiation);
            } else {
                await loadDetail(selectedId);
            }
            setPendingActionId(null);
            setActionMessage("");
            await load(collection, page);
        } catch (e) {
            showAlert(`Действие не выполнено: ${e.message || e}`, "error");
        } finally {
            setActionBusy(null);
        }
    };

    const handleActionClick = (action) => {
        if (!action?.enabled || actionBusy) return;
        if (actionNeedsMessage(action)) {
            setPendingActionId(action.id);
            return;
        }
        runAction(action.id, null);
    };

    const confirmPendingAction = () => {
        if (!pendingActionId) return;
        const payload = actionMessage.trim() ? { message: actionMessage.trim() } : {};
        runAction(pendingActionId, Object.keys(payload).length ? payload : null);
    };

    const visibleItems = filterNegotiationItems(items, {
        onlyUnviewed,
        filters: listFilters,
    });
    const localFilterActive = onlyUnviewed || hasNegotiationFilters(listFilters);

    const handleBulkImport = async () => {
        const targets = visibleItems.filter(
            (item) => item?.id && !importing[item.id] && !isAlreadyCandidate(item)
        );
        if (!targets.length) {
            const allIn = visibleItems.length > 0 && visibleItems.every((item) => isAlreadyCandidate(item));
            showAlert(allIn ? "Все выбранные уже в кандидатах" : "Нет откликов для импорта", "warning");
            return;
        }
        try {
            setBulkImporting(true);
            let ok = 0;
            let fail = 0;
            let skipped = visibleItems.length - targets.length;
            for (const item of targets) {
                try {
                    const res = await importHHNegotiation(hhVacancyId, item.id, { collection });
                    setImportedIds((prev) => ({ ...prev, [item.id]: true }));
                    if (res?.status === "already_exists" || res?.created === false) {
                        skipped += 1;
                    } else {
                        ok += 1;
                    }
                } catch {
                    fail += 1;
                }
            }
            const importedNow = new Set(targets.map((t) => t.id));
            setItems((prev) =>
                prev.map((row) => (importedNow.has(row.id) ? { ...row, already_candidate: true } : row))
            );
            showAlert(
                `Импорт завершён: новых ${ok}, уже в кандидатах ${skipped}, ошибок ${fail}`,
                fail ? "warning" : "success"
            );
        } finally {
            setBulkImporting(false);
        }
    };

    const resume = detail?.resume || {};
    const actions = enabledActions(detail?.actions);
    const hhLink = detail?.hh_url || resume.alternate_url;
    const resumeProfile = mapHhResumeToProfile(resume, {
        vacancyName,
        statusLabel: detail?.employer_state_name || detail?.state_name || detail?.state,
    });

    return (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center z-50 p-4">
            <div
                className="bg-white rounded-3xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col overflow-hidden ring-1 ring-slate-900/5 relative"
                data-testid="hh-negotiations-modal"
            >
                <div className="p-6 border-b border-slate-100 flex justify-between items-start bg-slate-50/50">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center text-yellow-600">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" /></svg>
                            </div>
                            <h2 className="text-2xl font-bold text-slate-900">Отклики HH.ru</h2>
                        </div>
                        <p className="text-sm font-medium text-slate-500 pl-13">
                            <span className="text-slate-700">{vacancyName || "Вакансия"}</span> <span className="text-slate-300 mx-1">•</span> ID {hhVacancyId}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="w-10 h-10 flex items-center justify-center rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-700 transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>

                <div className="p-6 border-b border-slate-100 flex flex-wrap gap-4 items-center bg-white">
                    <div className="relative">
                        <select
                            value={collection}
                            onChange={(e) => {
                                const next = e.target.value;
                                setCollection(next);
                                setSelectedId(null);
                                setDetail(null);
                                load(next, 0);
                            }}
                            className="appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all cursor-pointer min-w-[200px]"
                        >
                            {(collections.length
                                ? collections
                                : [{ id: "response", name: "Неразобранные" }]
                            ).map((c) => (
                                <option key={c.id} value={c.id}>
                                    {c.name || c.id} {c.counters?.total != null ? `(${c.counters.total})` : ""}
                                </option>
                            ))}
                        </select>
                        <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                        </div>
                    </div>

                    <span className="text-sm font-medium text-slate-500 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
                        Найдено: <span className="text-slate-900">{found}</span>
                        {localFilterActive ? ` · показ ${visibleItems.length}` : ""}
                    </span>

                    <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={onlyUnviewed}
                            onChange={(e) => setOnlyUnviewed(e.target.checked)}
                            className="rounded border-slate-300"
                        />
                        Только непросмотренные / с обновлениями
                    </label>

                    <button
                        type="button"
                        onClick={handleBulkImport}
                        disabled={bulkImporting || visibleItems.length === 0}
                        className="text-sm px-4 py-2.5 bg-[#e0bb48] text-black rounded-xl hover:bg-[#d4af3a] font-medium disabled:opacity-50"
                    >
                        {bulkImporting ? "Импорт..." : `Импорт всех (${visibleItems.length})`}
                    </button>

                    <button
                        type="button"
                        onClick={() => load(collection, page)}
                        className="ml-auto text-sm px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl hover:bg-slate-100 font-medium text-slate-700 transition-colors flex items-center gap-2"
                    >
                        <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                        Обновить
                    </button>
                </div>

                <HHNegotiationsFilters
                    filters={listFilters}
                    onChange={setListFilters}
                    items={items}
                    pages={pages}
                />

                <div className="flex-1 overflow-hidden bg-slate-50/30 flex min-h-0 relative">
                    <div className={`${selectedId ? "hidden lg:block lg:w-1/2 border-r border-slate-100" : "w-full"} overflow-y-auto p-6`}>
                        {loading ? (
                            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                                <svg className="animate-spin h-8 w-8 mb-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span className="font-medium">Загрузка откликов...</span>
                            </div>
                        ) : visibleItems.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-20 text-center">
                                <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mb-4 text-slate-300 shadow-sm border border-slate-100">
                                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" /></svg>
                                </div>
                                <h3 className="text-lg font-medium text-slate-700">Нет откликов</h3>
                                <p className="text-slate-500 mt-1">
                                    {localFilterActive
                                        ? "Никто не подходит под выбранные фильтры."
                                        : "В выбранной коллекции пусто."}
                                </p>
                            </div>
                        ) : (
                            <div className="grid gap-3">
                                {visibleItems.map((item) => {
                                    const r = item.resume || {};
                                    const selected = selectedId === item.id;
                                    const fio = formatHhFullName(r);
                                    return (
                                        <div
                                            key={item.id}
                                            role="button"
                                            tabIndex={0}
                                            data-testid={`negotiation-row-${item.id}`}
                                            onClick={() => handleSelect(item)}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter" || e.key === " ") {
                                                    e.preventDefault();
                                                    handleSelect(item);
                                                }
                                            }}
                                            className={`text-left bg-white border p-4 rounded-2xl shadow-sm transition-all flex gap-4 justify-between items-center cursor-pointer ${
                                                selected
                                                    ? "border-[#cda834] ring-2 ring-[#cda834]/30"
                                                    : "border-slate-200/80 hover:shadow-md hover:border-slate-300"
                                            }`}
                                        >
                                            <div className="flex-1 min-w-0 flex items-center gap-4">
                                                <div className="w-11 h-11 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 font-bold shrink-0 border border-slate-200">
                                                    {fio ? fio.charAt(0).toUpperCase() : "U"}
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="font-bold text-slate-900 truncate">
                                                        {fio || "Без имени"}
                                                    </div>
                                                    <div className="text-sm font-medium text-slate-600 truncate flex items-center gap-2 mt-0.5">
                                                        <span>{r.title || "—"}</span>
                                                        {r.age != null && (
                                                            <>
                                                                <span className="text-slate-300">•</span>
                                                                <span className="text-slate-500">{r.age} лет</span>
                                                            </>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-3 mt-2">
                                                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase bg-slate-100 text-slate-500 border border-slate-200/60">
                                                            {item.state_name || item.state || "—"}
                                                        </span>
                                                        {item.created_at && (
                                                            <span className="text-xs font-medium text-slate-400">
                                                                {new Date(item.created_at).toLocaleString("ru-RU", {
                                                                    day: "numeric",
                                                                    month: "short",
                                                                    hour: "2-digit",
                                                                    minute: "2-digit",
                                                                })}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex flex-col gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                                                {isAlreadyCandidate(item) ? (
                                                    <span className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-2 rounded-xl text-center">
                                                        Уже в кандидатах
                                                    </span>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        disabled={importing[item.id]}
                                                        onClick={() => handleImport(item)}
                                                        className="text-sm bg-[#e0bb48] text-black px-3 py-2 rounded-xl hover:bg-[#d4af3a] disabled:opacity-50 font-medium"
                                                    >
                                                        {importing[item.id] ? "..." : "В кандидаты"}
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {selectedId && (
                        <div
                            className="flex w-full lg:w-1/2 flex-col overflow-y-auto p-6 bg-white absolute inset-0 lg:static z-10"
                            data-testid="negotiation-detail"
                        >
                            {detailLoading && !detail ? (
                                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                                    <svg className="animate-spin h-7 w-7 mb-3" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Загрузка карточки...
                                </div>
                            ) : !detail ? (
                                <p className="text-slate-500 text-sm">Не удалось загрузить детали.</p>
                            ) : (
                                <>
                                    <div className="flex items-start justify-between gap-3 mb-4">
                                        <div>
                                            <h3 className="text-xl font-bold text-slate-900">
                                                {formatHhFullName(resume) || "Без имени"}
                                            </h3>
                                            <p className="text-sm text-slate-600 mt-1">{resume.title || "—"}</p>
                                        </div>
                                        <button
                                            type="button"
                                            className="text-xs text-slate-500 hover:text-slate-800"
                                            onClick={() => {
                                                setSelectedId(null);
                                                setDetail(null);
                                                setResumeCardOpen(false);
                                            }}
                                        >
                                            Закрыть
                                        </button>
                                    </div>

                                    <dl className="grid grid-cols-2 gap-3 text-sm mb-5">
                                        <div>
                                            <dt className="text-slate-400 text-xs uppercase tracking-wide">Возраст</dt>
                                            <dd className="font-medium text-slate-800">{resume.age ?? "—"}</dd>
                                        </div>
                                        <div>
                                            <dt className="text-slate-400 text-xs uppercase tracking-wide">Город</dt>
                                            <dd className="font-medium text-slate-800">{resume.area || "—"}</dd>
                                        </div>
                                        <div>
                                            <dt className="text-slate-400 text-xs uppercase tracking-wide">Опыт</dt>
                                            <dd className="font-medium text-slate-800">
                                                {formatExperienceMonths(resume.experience_months) || "—"}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-slate-400 text-xs uppercase tracking-wide">Зарплата</dt>
                                            <dd className="font-medium text-slate-800">
                                                {resume.salary_amount != null
                                                    ? `${resume.salary_amount} ${resume.salary_currency || ""}`.trim()
                                                    : "—"}
                                            </dd>
                                        </div>
                                        <div className="col-span-2">
                                            <dt className="text-slate-400 text-xs uppercase tracking-wide">Статус на HH</dt>
                                            <dd className="font-medium text-slate-800">
                                                {detail.employer_state_name || detail.state_name || detail.state || "—"}
                                            </dd>
                                        </div>
                                    </dl>

                                    {Array.isArray(resume.skill_set) && resume.skill_set.length > 0 && (
                                        <div className="mb-5">
                                            <div className="text-slate-400 text-xs uppercase tracking-wide mb-2">Навыки</div>
                                            <div className="flex flex-wrap gap-1.5">
                                                {resume.skill_set.slice(0, 12).map((s) => (
                                                    <span
                                                        key={s}
                                                        className="text-xs px-2 py-1 rounded-lg bg-slate-50 border border-slate-100 text-slate-600"
                                                    >
                                                        {s}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    <div className="flex flex-wrap gap-2 mb-6">
                                        <button
                                            type="button"
                                            data-testid="negotiation-resume-open"
                                            onClick={() => setResumeCardOpen(true)}
                                            className="text-sm px-4 py-2.5 rounded-xl bg-slate-900 text-white hover:bg-slate-800 font-medium"
                                        >
                                            Подробнее
                                        </button>
                                        {hhLink && (
                                            <a
                                                href={hhLink}
                                                target="_blank"
                                                rel="noreferrer"
                                                data-testid="hh-external-link"
                                                className="text-sm px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 font-medium text-slate-700 inline-flex items-center gap-2"
                                            >
                                                Открыть на HH.ru
                                            </a>
                                        )}
                                        {isAlreadyCandidate(detail) || isAlreadyCandidate({ id: selectedId }) ? (
                                            <span className="text-sm px-4 py-2.5 rounded-xl bg-slate-100 text-slate-600 font-medium">
                                                Уже в кандидатах
                                            </span>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => handleImport({ id: selectedId, already_candidate: detail.already_candidate })}
                                                disabled={importing[selectedId]}
                                                className="text-sm px-4 py-2.5 rounded-xl bg-[#e0bb48] text-black hover:bg-[#d4af3a] font-medium disabled:opacity-50"
                                            >
                                                {importing[selectedId] ? "Импорт..." : "В кандидаты"}
                                            </button>
                                        )}
                                    </div>

                                    <div className="border-t border-slate-100 pt-4">
                                        <h4 className="text-sm font-semibold text-slate-800 mb-3">
                                            Действия на HH.ru
                                        </h4>
                                        {actions.length === 0 ? (
                                            <p className="text-sm text-slate-500">Нет доступных действий для этого отклика.</p>
                                        ) : (
                                            <div className="flex flex-wrap gap-2" data-testid="hh-actions">
                                                {actions.map((action) => (
                                                    <button
                                                        key={action.id}
                                                        type="button"
                                                        data-testid={`hh-action-${action.id}`}
                                                        disabled={!!actionBusy}
                                                        onClick={() => handleActionClick(action)}
                                                        className={`text-sm px-3 py-2 rounded-xl border font-medium disabled:opacity-50 ${
                                                            ACTION_BTN_CLASS[actionButtonVariant(action.id)]
                                                        }`}
                                                    >
                                                        {actionBusy === action.id
                                                            ? "..."
                                                            : hhActionLabel(action)}
                                                    </button>
                                                ))}
                                            </div>
                                        )}

                                        {pendingActionId && (
                                            <div
                                                className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200"
                                                data-testid="action-message-form"
                                            >
                                                <label className="block text-sm font-medium text-slate-700 mb-2">
                                                    Сообщение кандидату (необязательно)
                                                </label>
                                                <textarea
                                                    value={actionMessage}
                                                    onChange={(e) => setActionMessage(e.target.value)}
                                                    rows={3}
                                                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#cda834]/40"
                                                    placeholder="Текст сообщения для HH.ru"
                                                />
                                                <div className="flex gap-2 mt-3">
                                                    <button
                                                        type="button"
                                                        onClick={confirmPendingAction}
                                                        disabled={!!actionBusy}
                                                        className="text-sm px-4 py-2 rounded-xl bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50"
                                                    >
                                                        Подтвердить
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setPendingActionId(null);
                                                            setActionMessage("");
                                                        }}
                                                        className="text-sm px-4 py-2 rounded-xl border border-slate-200 text-slate-600"
                                                    >
                                                        Отмена
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                </div>

                {pages > 1 && (
                    <div className="p-5 border-t border-slate-100 bg-white flex justify-between items-center">
                        <button
                            type="button"
                            disabled={page <= 0 || loading}
                            onClick={() => load(collection, page - 1)}
                            className="text-sm px-4 py-2 border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 font-medium text-slate-700 transition-colors"
                        >
                            Назад
                        </button>
                        <span className="text-sm font-medium text-slate-500 bg-slate-50 px-3 py-1 rounded-lg">
                            Стр. <span className="text-slate-900">{page + 1}</span> из <span className="text-slate-900">{pages}</span>
                        </span>
                        <button
                            type="button"
                            disabled={page + 1 >= pages || loading}
                            onClick={() => load(collection, page + 1)}
                            className="text-sm px-4 py-2 border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 font-medium text-slate-700 transition-colors"
                        >
                            Вперёд
                        </button>
                    </div>
                )}
                <NegotiationResumeModal
                    open={resumeCardOpen && !!detail}
                    onClose={() => setResumeCardOpen(false)}
                    candidate={resumeProfile}
                    vacancyTitle={vacancyName || resume.title}
                    statusLabel={detail?.employer_state_name || detail?.state_name || detail?.state}
                    hhLink={resume.alternate_url || hhLink}
                    alreadyCandidate={isAlreadyCandidate(detail) || isAlreadyCandidate({ id: selectedId })}
                    importing={importing[selectedId]}
                    onImport={() => handleImport({ id: selectedId, already_candidate: detail?.already_candidate })}
                />
            </div>
        </div>
    );
}
