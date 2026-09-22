import {
    EMPTY_NEGOTIATION_FILTERS,
    EXPERIENCE_OPTIONS,
    WORK_FORMAT_OPTIONS,
    hasNegotiationFilters,
    negotiationFilterAgeError,
    uniqueResumeCities,
} from "../../utils/negotiationListFilters";

const inputClass =
    "border border-slate-200 rounded-xl px-3 py-2 text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834]";

export default function HHNegotiationsFilters({ filters, onChange, items, pages = 0 }) {
    const cities = uniqueResumeCities(items);
    const ageError = negotiationFilterAgeError(filters);
    const active = hasNegotiationFilters(filters);

    const setField = (key, value) => onChange({ ...filters, [key]: value });

    return (
        <div className="px-6 pb-5 pt-0 border-b border-slate-100 bg-white" data-testid="hh-negotiations-filters">
            <div className="flex flex-wrap gap-3 items-end">
                <label className="flex flex-col gap-1 min-w-[160px] flex-1">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Город</span>
                    <input
                        list="hh-negotiation-cities"
                        value={filters.city}
                        onChange={(e) => setField("city", e.target.value)}
                        placeholder="Любой"
                        className={inputClass}
                        data-testid="filter-city"
                    />
                    <datalist id="hh-negotiation-cities">
                        {cities.map((city) => (
                            <option key={city} value={city} />
                        ))}
                    </datalist>
                </label>

                <label className="flex flex-col gap-1 w-[88px]">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Возраст от</span>
                    <input
                        type="number"
                        min={0}
                        max={120}
                        value={filters.age_from}
                        onChange={(e) => setField("age_from", e.target.value)}
                        placeholder="—"
                        className={inputClass}
                        data-testid="filter-age-from"
                    />
                </label>

                <label className="flex flex-col gap-1 w-[88px]">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Возраст до</span>
                    <input
                        type="number"
                        min={0}
                        max={120}
                        value={filters.age_to}
                        onChange={(e) => setField("age_to", e.target.value)}
                        placeholder="—"
                        className={inputClass}
                        data-testid="filter-age-to"
                    />
                </label>

                <label className="flex flex-col gap-1 min-w-[160px]">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Опыт работы</span>
                    <select
                        value={filters.experience}
                        onChange={(e) => setField("experience", e.target.value)}
                        className={`${inputClass} cursor-pointer`}
                        data-testid="filter-experience"
                    >
                        <option value="">Любой</option>
                        {EXPERIENCE_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                                {o.label}
                            </option>
                        ))}
                    </select>
                </label>

                <label className="flex flex-col gap-1 min-w-[160px]">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Формат работы</span>
                    <select
                        value={filters.work_format}
                        onChange={(e) => setField("work_format", e.target.value)}
                        className={`${inputClass} cursor-pointer`}
                        data-testid="filter-work-format"
                    >
                        <option value="">Любой</option>
                        {WORK_FORMAT_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                                {o.label}
                            </option>
                        ))}
                    </select>
                </label>

                {active ? (
                    <button
                        type="button"
                        onClick={() => onChange({ ...EMPTY_NEGOTIATION_FILTERS })}
                        className="text-sm px-3 py-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
                        data-testid="filter-reset"
                    >
                        Сбросить
                    </button>
                ) : null}
            </div>
            {ageError ? (
                <p className="text-xs text-red-600 mt-2">{ageError}</p>
            ) : null}
            {active && pages > 1 ? (
                <p className="text-xs text-slate-400 mt-2">
                    Фильтр применяется к откликам на текущей странице.
                </p>
            ) : null}
        </div>
    );
}
