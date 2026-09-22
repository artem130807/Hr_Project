import { useEffect, useState } from "react";
import {
    listVacancyFilters,
    createVacancyFilter,
    updateVacancyFilter,
    assignFilterToVacancy,
    unassignFilterFromVacancy,
    runVacancyFilterNow,
    formatFilterRunSummary,
} from "../../services/vacancyFilterApi";
import {
    WORK_FORMAT_OPTIONS,
    EXPERIENCE_OPTIONS,
    formatFilterTitle,
    formatFilterSummary,
    labelWorkFormat,
    labelExperience,
    labelFilterAction,
    validateFilterForm,
    normalizeFilterPayload,
    filterToForm,
    ACTION_OPTIONS,
} from "../../utils/vacancyFilterLabels";
import { useAlertContext } from "../../context/AlertContext";

const emptyForm = filterToForm(null);

/**
 * Filter setup for a vacancy:
 * - post-create (`allowSkip`): select / create / skip
 * - manage existing (`allowSkip=false`): select / create / edit current / unassign
 */
export default function VacancyFilterStepModal({
    vacancy,
    onDone,
    onSkip,
    allowSkip = true,
}) {
    const { showAlert } = useAlertContext();
    const hasAssigned = Boolean(vacancy?.filter_id);
    const [mode, setMode] = useState(hasAssigned && !allowSkip ? "edit" : "select");
    const [filters, setFilters] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [selectedId, setSelectedId] = useState(vacancy?.filter_id ?? null);
    const [form, setForm] = useState(emptyForm);
    const [formErrors, setFormErrors] = useState({});
    const [editFilterId, setEditFilterId] = useState(vacancy?.filter_id ?? null);
    const [runningFilter, setRunningFilter] = useState(false);

    const vacancyName = vacancy?.name || `#${vacancy?.id}`;
    const selected = filters.find((f) => f.id === selectedId) || null;
    const closeLabel = allowSkip ? "Пропустить" : "Закрыть";
    const canRunFilter =
        Boolean(vacancy?.id && vacancy?.filter_id) &&
        Boolean(vacancy?.hh_vacancy_id || vacancy?.hh_vacancy_url);

    const handleRunFilterNow = async () => {
        if (!vacancy?.id || !canRunFilter) return;
        setRunningFilter(true);
        try {
            showAlert("Прогоняем фильтр по откликам HH (порция отказов)…", "info");
            const result = await runVacancyFilterNow(vacancy.id);
            const { msg, level } = formatFilterRunSummary(result?.summary || result || {});
            showAlert(msg, level);
        } catch (e) {
            showAlert(`Не удалось прогнать фильтр: ${e?.message || e}`, "error");
        } finally {
            setRunningFilter(false);
        }
    };

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                setLoading(true);
                const data = await listVacancyFilters();
                if (cancelled) return;
                const list = Array.isArray(data) ? data : [];
                setFilters(list);

                const assignedId = vacancy?.filter_id ?? null;
                if (assignedId) {
                    setSelectedId(assignedId);
                    setEditFilterId(assignedId);
                    const current = list.find((f) => f.id === assignedId);
                    if (current) setForm(filterToForm(current));
                    if (!allowSkip) setMode("edit");
                } else if (list.length === 0) {
                    setMode("create");
                } else {
                    setMode("select");
                }
            } catch (e) {
                if (!cancelled) {
                    showAlert(`Не удалось загрузить фильтры: ${e.message || e}`, "error");
                    setMode(hasAssigned ? "edit" : "create");
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [vacancy?.id, vacancy?.filter_id]);

    const handleClose = () => {
        if (allowSkip) onSkip?.();
        else onSkip?.() ?? onDone?.(vacancy);
    };

    const handleApplyExisting = async () => {
        if (!selectedId || !vacancy?.id) return;
        setSaving(true);
        try {
            const updated = await assignFilterToVacancy(vacancy.id, selectedId);
            showAlert("Фильтр привязан к вакансии", "success");
            onDone?.(updated);
        } catch (e) {
            showAlert(e?.message || "Не удалось привязать фильтр", "error");
        } finally {
            setSaving(false);
        }
    };

    const handleCreateAndApply = async () => {
        if (!vacancy?.id) return;
        const errors = validateFilterForm(form);
        setFormErrors(errors);
        if (Object.keys(errors).length > 0) return;

        setSaving(true);
        try {
            const created = await createVacancyFilter(normalizeFilterPayload(form));
            const updated = await assignFilterToVacancy(vacancy.id, created.id);
            showAlert("Фильтр создан и привязан к вакансии", "success");
            onDone?.(updated);
        } catch (e) {
            showAlert(e?.message || "Не удалось создать фильтр", "error");
        } finally {
            setSaving(false);
        }
    };

    const handleSaveEdit = async () => {
        if (!editFilterId || !vacancy?.id) return;
        const errors = validateFilterForm(form);
        setFormErrors(errors);
        if (Object.keys(errors).length > 0) return;

        setSaving(true);
        try {
            await updateVacancyFilter(editFilterId, normalizeFilterPayload(form));
            // Ensure vacancy still points at this filter (no-op if already set)
            const updated =
                vacancy.filter_id === editFilterId
                    ? { ...vacancy, filter_id: editFilterId }
                    : await assignFilterToVacancy(vacancy.id, editFilterId);
            showAlert("Фильтр обновлён", "success");
            onDone?.(updated?.id ? updated : { ...vacancy, filter_id: editFilterId });
        } catch (e) {
            showAlert(e?.message || "Не удалось сохранить фильтр", "error");
        } finally {
            setSaving(false);
        }
    };

    const handleUnassign = async () => {
        if (!vacancy?.id) return;
        setSaving(true);
        try {
            const updated = await unassignFilterFromVacancy(vacancy.id);
            showAlert("Фильтр отвязан от вакансии", "success");
            onDone?.(updated);
        } catch (e) {
            showAlert(e?.message || "Не удалось отвязать фильтр", "error");
        } finally {
            setSaving(false);
        }
    };

    const openEditFor = (filter) => {
        if (!filter) return;
        setEditFilterId(filter.id);
        setSelectedId(filter.id);
        setForm(filterToForm(filter));
        setFormErrors({});
        setMode("edit");
    };

    const tabs = [
        { id: "select", label: "Выбрать" },
        { id: "create", label: "Создать новый" },
        ...(hasAssigned || editFilterId
            ? [{ id: "edit", label: "Редактировать" }]
            : []),
    ];

    return (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-start z-[60] overflow-y-auto py-8 px-4">
            <div className="bg-white p-6 rounded-2xl shadow-xl w-full max-w-2xl ring-1 ring-slate-900/5">
                <div className="mb-5">
                    <h2 className="text-xl font-bold text-slate-900">
                        Фильтр для вакансии «{vacancyName}»
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">
                        {allowSkip
                            ? "Выберите существующий фильтр или создайте новый. Можно пропустить — вакансия уже сохранена."
                            : "Измените параметры фильтра, выберите другой или отвяжите фильтр от вакансии."}
                    </p>
                    {hasAssigned && (
                        <p className="mt-2 text-xs text-slate-500">
                            Сейчас привязан фильтр #{vacancy.filter_id}
                            {selected && selected.id === vacancy.filter_id
                                ? ` · ${formatFilterSummary(selected)}`
                                : ""}
                        </p>
                    )}
                    {canRunFilter && (
                        <div className="mt-3">
                            <button
                                type="button"
                                data-testid="filter-run-now"
                                onClick={handleRunFilterNow}
                                disabled={runningFilter || saving}
                                className="text-sm px-3 py-2 rounded-xl bg-[#cda834]/15 text-slate-800 hover:bg-[#cda834]/25 border border-[#cda834]/40 font-medium disabled:opacity-50"
                            >
                                {runningFilter
                                    ? "Прогон фильтра…"
                                    : "Прогнать фильтр сейчас"}
                            </button>
                            <p className="mt-1.5 text-xs text-slate-400">
                                Отправит отказ на HH непросмотренным откликам, которые не проходят
                                критерии. Уже просмотренные не трогаются.
                            </p>
                        </div>
                    )}
                    {hasAssigned && !canRunFilter && (
                        <p className="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2">
                            Чтобы прогнать фильтр, вакансия должна быть опубликована или привязана к
                            HH.ru.
                        </p>
                    )}
                </div>

                <div className="flex gap-2 mb-5 border-b border-slate-200 flex-wrap">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            onClick={() => {
                                if (tab.id === "edit" && editFilterId) {
                                    const current =
                                        filters.find((f) => f.id === editFilterId) ||
                                        filters.find((f) => f.id === vacancy?.filter_id);
                                    if (current) openEditFor(current);
                                    else setMode("edit");
                                } else {
                                    setMode(tab.id);
                                }
                            }}
                            className={`pb-2.5 px-3 text-sm font-medium relative ${
                                mode === tab.id ? "text-[#cda834]" : "text-slate-500"
                            }`}
                        >
                            {tab.label}
                            {mode === tab.id && (
                                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#cda834]" />
                            )}
                        </button>
                    ))}
                </div>

                {loading ? (
                    <div className="py-10 text-center text-slate-400 text-sm">Загрузка фильтров…</div>
                ) : mode === "select" ? (
                    <div className="space-y-4">
                        {filters.length === 0 ? (
                            <p className="text-sm text-slate-500">
                                Пока нет сохранённых фильтров. Создайте новый.
                            </p>
                        ) : (
                            <div className="grid gap-2 max-h-56 overflow-y-auto">
                                {filters.map((f) => (
                                    <button
                                        key={f.id}
                                        type="button"
                                        onClick={() => setSelectedId(f.id)}
                                        className={`text-left px-4 py-3 rounded-xl border transition-colors ${
                                            selectedId === f.id
                                                ? "border-[#cda834] bg-[#cda834]/10"
                                                : "border-slate-200 hover:border-slate-300 bg-white"
                                        }`}
                                    >
                                        <div className="font-medium text-slate-900 text-sm flex items-center gap-2">
                                            {formatFilterTitle(f)}
                                            {f.id === vacancy?.filter_id && (
                                                <span className="text-[10px] uppercase tracking-wide text-green-700 bg-green-50 border border-green-100 px-1.5 py-0.5 rounded">
                                                    Текущий
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">
                                            {formatFilterSummary(f)}
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}

                        {selected && (
                            <div
                                data-testid="filter-details"
                                className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm space-y-2"
                            >
                                <div className="font-semibold text-slate-800">Параметры фильтра</div>
                                <DetailRow label="Город" value={selected.city || "—"} />
                                <DetailRow
                                    label="Возраст"
                                    value={
                                        selected.age_from != null || selected.age_to != null
                                            ? `${selected.age_from ?? "…"}–${selected.age_to ?? "…"}`
                                            : "—"
                                    }
                                />
                                <DetailRow
                                    label="Опыт"
                                    value={labelExperience(selected.experience)}
                                />
                                <DetailRow
                                    label="Формат работы"
                                    value={labelWorkFormat(selected.work_format)}
                                />
                                <DetailRow
                                    label="Статус HH"
                                    value={labelFilterAction(selected.action)}
                                />
                                <button
                                    type="button"
                                    data-testid="filter-edit-selected"
                                    onClick={() => openEditFor(selected)}
                                    className="mt-2 text-sm text-[#8a7020] hover:underline font-medium"
                                >
                                    Редактировать этот фильтр
                                </button>
                            </div>
                        )}

                        <div className="flex flex-wrap gap-2 justify-end pt-2">
                            <button
                                type="button"
                                onClick={handleClose}
                                className="px-4 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-700 hover:bg-slate-50"
                                disabled={saving}
                            >
                                {closeLabel}
                            </button>
                            {!allowSkip && hasAssigned && (
                                <button
                                    type="button"
                                    data-testid="filter-unassign"
                                    onClick={handleUnassign}
                                    disabled={saving}
                                    className="px-4 py-2.5 rounded-xl border border-red-200 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                                >
                                    Отвязать
                                </button>
                            )}
                            <button
                                type="button"
                                onClick={handleApplyExisting}
                                disabled={!selectedId || saving}
                                className="px-4 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
                            >
                                {saving ? "Сохранение…" : "Применить"}
                            </button>
                        </div>
                    </div>
                ) : mode === "edit" ? (
                    <div className="space-y-4">
                        {!editFilterId ? (
                            <p className="text-sm text-slate-500">
                                Сначала выберите фильтр на вкладке «Выбрать».
                            </p>
                        ) : (
                            <>
                                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2">
                                    Правки фильтра #{editFilterId} применятся ко всем вакансиям, к
                                    которым он привязан.
                                </p>
                                <FilterFormFields
                                    form={form}
                                    setForm={setForm}
                                    formErrors={formErrors}
                                    idPrefix="vf-edit"
                                />
                            </>
                        )}

                        <div className="flex flex-wrap gap-2 justify-end pt-2">
                            <button
                                type="button"
                                onClick={handleClose}
                                className="px-4 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-700 hover:bg-slate-50"
                                disabled={saving}
                            >
                                {closeLabel}
                            </button>
                            {!allowSkip && hasAssigned && (
                                <button
                                    type="button"
                                    data-testid="filter-unassign"
                                    onClick={handleUnassign}
                                    disabled={saving}
                                    className="px-4 py-2.5 rounded-xl border border-red-200 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                                >
                                    Отвязать
                                </button>
                            )}
                            <button
                                type="button"
                                data-testid="filter-save-edit"
                                onClick={handleSaveEdit}
                                disabled={!editFilterId || saving}
                                className="px-4 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
                            >
                                {saving ? "Сохранение…" : "Сохранить изменения"}
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <FilterFormFields
                            form={form}
                            setForm={setForm}
                            formErrors={formErrors}
                            idPrefix="vf-create"
                        />

                        <div className="flex flex-wrap gap-2 justify-end pt-2">
                            <button
                                type="button"
                                onClick={handleClose}
                                className="px-4 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-700 hover:bg-slate-50"
                                disabled={saving}
                            >
                                {closeLabel}
                            </button>
                            <button
                                type="button"
                                onClick={handleCreateAndApply}
                                disabled={saving}
                                className="px-4 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
                            >
                                {saving ? "Сохранение…" : "Создать и применить"}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function FilterFormFields({ form, setForm, formErrors, idPrefix }) {
    return (
        <>
            <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    Статус на HH
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {ACTION_OPTIONS.map((o) => {
                        const checked = (form.action || "discard") === o.value;
                        return (
                            <label
                                key={o.value}
                                className={`flex items-start gap-2 rounded-xl border px-3 py-2.5 cursor-pointer ${
                                    checked
                                        ? "border-[#cda834] bg-[#cda834]/10"
                                        : "border-slate-200 bg-slate-50"
                                }`}
                            >
                                <input
                                    type="radio"
                                    name={`${idPrefix}-action`}
                                    value={o.value}
                                    checked={checked}
                                    onChange={() => setForm((p) => ({ ...p, action: o.value }))}
                                    className="mt-1"
                                />
                                <span>
                                    <span className="block text-sm font-medium text-slate-800">{o.label}</span>
                                    <span className="block text-xs text-slate-500 mt-0.5">{o.hint}</span>
                                </span>
                            </label>
                        );
                    })}
                </div>
            </div>

            {formErrors.criteria && (
                <p className="text-xs text-red-600">{formErrors.criteria}</p>
            )}

            <Field label="Город" htmlFor={`${idPrefix}-city`} optional>
                <input
                    id={`${idPrefix}-city`}
                    value={form.city}
                    onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/40"
                    placeholder="Например, Москва"
                />
            </Field>

            <div className="grid grid-cols-2 gap-3">
                <Field label="Возраст от" htmlFor={`${idPrefix}-age-from`} optional>
                    <input
                        id={`${idPrefix}-age-from`}
                        type="number"
                        min={0}
                        max={120}
                        value={form.age_from}
                        onChange={(e) => setForm((p) => ({ ...p, age_from: e.target.value }))}
                        className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/40"
                    />
                </Field>
                <Field label="Возраст до" htmlFor={`${idPrefix}-age-to`} optional>
                    <input
                        id={`${idPrefix}-age-to`}
                        type="number"
                        min={0}
                        max={120}
                        value={form.age_to}
                        onChange={(e) => setForm((p) => ({ ...p, age_to: e.target.value }))}
                        className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/40"
                    />
                </Field>
            </div>
            {formErrors.age && (
                <p className="text-xs text-red-600 -mt-2">{formErrors.age}</p>
            )}

            <Field label="Опыт работы" htmlFor={`${idPrefix}-experience`} optional>
                <select
                    id={`${idPrefix}-experience`}
                    value={form.experience}
                    onChange={(e) => setForm((p) => ({ ...p, experience: e.target.value }))}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/40"
                >
                    <option value="">Не указан</option>
                    {EXPERIENCE_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                            {o.label}
                        </option>
                    ))}
                </select>
            </Field>

            <Field label="Формат работы" htmlFor={`${idPrefix}-work-format`} optional>
                <select
                    id={`${idPrefix}-work-format`}
                    value={form.work_format}
                    onChange={(e) => setForm((p) => ({ ...p, work_format: e.target.value }))}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/40"
                >
                    <option value="">Не указан</option>
                    {WORK_FORMAT_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                            {o.label}
                        </option>
                    ))}
                </select>
            </Field>
        </>
    );
}

function Field({ label, htmlFor, children, optional = false }) {
    return (
        <div>
            <label
                htmlFor={htmlFor}
                className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5"
            >
                {label}
                {optional ? (
                    <span className="font-normal normal-case tracking-normal text-slate-400">
                        {" "}
                        — не обязательно
                    </span>
                ) : null}
            </label>
            {children}
        </div>
    );
}

function DetailRow({ label, value }) {
    return (
        <div className="flex gap-2">
            <span className="text-slate-500 w-28 shrink-0">{label}</span>
            <span className="text-slate-900 font-medium">{value}</span>
        </div>
    );
}
