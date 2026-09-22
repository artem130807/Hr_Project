import React from "react";
import { Link } from "react-router-dom";
import { CANDIDATE_CATEGORIES } from "../../utils/candidateCategories";
import AutoNegotiationsToggle from "../hh/AutoNegotiationsToggle";

/**
 * Candidates list filters: search, status, HH vacancy checkboxes, category, perfect.
 */
export default function CandidatesFilters({
    searchQuery,
    onSearchChange,
    statusFilter,
    statusDict,
    onStatusChange,
    vacancyOptions,
    selectedVacancyIds,
    onToggleVacancy,
    onClearVacancies,
    vacanciesLoading,
    unboundHhCount = 0,
    categoryFilter,
    onCategoryChange,
    onlyPerfect,
    onOnlyPerfectChange,
}) {
    const selected = new Set((selectedVacancyIds || []).map(String));

    return (
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200/60 space-y-4">
            <div className="flex flex-wrap gap-4 items-end">
                <div className="flex-1 min-w-[200px]">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                        Поиск
                    </label>
                    <div className="relative">
                        <input
                            type="text"
                            placeholder="ФИО, телефон, скиллы..."
                            value={searchQuery}
                            onChange={(e) => onSearchChange(e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all"
                            data-testid="candidates-search"
                        />
                        <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-slate-400">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                                />
                            </svg>
                        </div>
                    </div>
                </div>

                <div className="w-full sm:w-48">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                        Статус
                    </label>
                    <select
                        value={statusFilter ? String(statusFilter.code ?? statusFilter.id ?? statusFilter) : ""}
                        onChange={onStatusChange}
                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all appearance-none cursor-pointer"
                        data-testid="candidates-status-filter"
                    >
                        <option value="">Все статусы</option>
                        {statusDict.map((s) => (
                            <option key={s.id} value={String(s.code ?? s.id)}>
                                {s.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="w-full sm:w-48">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                        Категория
                    </label>
                    <select
                        value={categoryFilter}
                        onChange={(e) => onCategoryChange(e.target.value)}
                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all appearance-none cursor-pointer"
                        data-testid="candidates-category-filter"
                    >
                        <option value="">Все категории</option>
                        {CANDIDATE_CATEGORIES.map((c) => (
                            <option key={c.id} value={c.id}>
                                {c.label || c.name}
                            </option>
                        ))}
                    </select>
                </div>

                <label className="flex items-center gap-2 cursor-pointer h-[42px] px-4 rounded-xl bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-colors">
                    <input
                        type="checkbox"
                        id="onlyPerfect"
                        checked={onlyPerfect}
                        onChange={(e) => onOnlyPerfectChange(e.target.checked)}
                        className="w-4 h-4 text-[#4f46e5] bg-white border-slate-300 rounded focus:ring-[#4f46e5] focus:ring-2 cursor-pointer"
                        data-testid="candidates-perfect-filter"
                    />
                    <span className="text-sm font-medium text-slate-700 select-none">Идеальные</span>
                </label>

                <AutoNegotiationsToggle className="ml-auto" />
            </div>

            <div data-testid="candidates-vacancy-filter">
                <div className="flex items-center justify-between gap-2 mb-2">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
                        Вакансии HH.ru (привязанные к платформе)
                    </label>
                    {selected.size > 0 && (
                        <button
                            type="button"
                            onClick={onClearVacancies}
                            className="text-xs text-slate-500 hover:text-slate-800 underline"
                            data-testid="candidates-vacancy-clear"
                        >
                            Сбросить
                        </button>
                    )}
                </div>
                {vacanciesLoading ? (
                    <p className="text-sm text-slate-400">Загрузка вакансий…</p>
                ) : vacancyOptions.length === 0 ? (
                    <p className="text-sm text-slate-500" data-testid="candidates-vacancy-empty">
                        {unboundHhCount > 0 ? (
                            <>
                                На HH есть {unboundHhCount}{" "}
                                {unboundHhCount === 1 ? "вакансия" : "вакансий"}, но они ещё не
                                привязаны к платформе — поэтому здесь пусто и фильтр по ним
                                недоступен.{" "}
                                <Link
                                    to="/vacancies?tab=hh"
                                    className="text-[#a88a1f] underline hover:text-slate-900"
                                >
                                    Вакансии → С HH.ru → Импортировать
                                </Link>
                            </>
                        ) : (
                            <>
                                Нет вакансий с привязкой к HH. Опубликуйте из вкладки «В платформе»
                                или импортируйте на{" "}
                                <Link
                                    to="/vacancies?tab=hh"
                                    className="text-[#a88a1f] underline hover:text-slate-900"
                                >
                                    Вакансии → С HH.ru
                                </Link>
                                .
                            </>
                        )}
                    </p>
                ) : (
                    <div className="flex flex-wrap gap-2 max-h-36 overflow-y-auto pr-1">
                        {vacancyOptions.map((v) => {
                            const id = String(v.id);
                            const checked = selected.has(id);
                            return (
                                <label
                                    key={v.id}
                                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border text-sm cursor-pointer transition-colors ${
                                        checked
                                            ? "bg-[#4f46e5]/15 border-[#4f46e5] text-slate-900"
                                            : "bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100"
                                    }`}
                                >
                                    <input
                                        type="checkbox"
                                        className="w-3.5 h-3.5 text-[#4f46e5] rounded border-slate-300 focus:ring-[#4f46e5]"
                                        checked={checked}
                                        onChange={() => onToggleVacancy(v.id)}
                                        data-testid={`vacancy-option-${v.id}`}
                                    />
                                    <span className="max-w-[220px] truncate" title={v.name}>
                                        {v.name}
                                    </span>
                                </label>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
