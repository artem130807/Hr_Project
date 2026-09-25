import { useCallback, useEffect, useMemo, useState } from "react";
import MainLayout from "../layout/MainLayout";
import { getPsychResult, listPsychResults } from "../services/psychTestApi";
import {
    getPublicProfessionalResult,
    listPublicProfessionalResults,
} from "../services/publicProfessionalTestApi";
import { useAlertContext } from "../context/AlertContext";
import PsychResultReport from "../components/psych/PsychResultReport";
import ProfResultReport from "../components/professional-test/ProfResultReport";

function typeLabel(kind) {
    if (kind === "psychological") return "Психологический";
    if (kind === "professional") return "Профессиональный";
    return "—";
}

function profSummary(row) {
    if (row.score != null && row.max_score != null) {
        return `${row.score}/${row.max_score}`;
    }
    if (row.timed_out) return "Время вышло";
    return "Ответы";
}

export default function PsychResultsPage() {
    const { showAlert } = useAlertContext();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selected, setSelected] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [typeFilter, setTypeFilter] = useState("all");
    const [fioQuery, setFioQuery] = useState("");
    const [specialtyQuery, setSpecialtyQuery] = useState("");
    const [appliedFio, setAppliedFio] = useState("");
    const [appliedSpecialty, setAppliedSpecialty] = useState("");

    const load = useCallback(async () => {
        try {
            setLoading(true);
            const filters = {
                q: appliedFio || undefined,
                position: appliedSpecialty || undefined,
            };
            const wantPsych = typeFilter === "all" || typeFilter === "psychological";
            const wantProf = typeFilter === "all" || typeFilter === "professional";

            const [psychRaw, profRaw] = await Promise.all([
                wantPsych ? listPsychResults(filters) : Promise.resolve([]),
                wantProf ? listPublicProfessionalResults(filters) : Promise.resolve([]),
            ]);

            const psychItems = (Array.isArray(psychRaw) ? psychRaw : psychRaw?.items || []).map(
                (row) => ({
                    ...row,
                    _kind: "psychological",
                    _key: `psych-${row.id}`,
                    _title: "Психологический опросник",
                })
            );
            const profItems = (Array.isArray(profRaw) ? profRaw : profRaw?.items || []).map(
                (row) => ({
                    ...row,
                    _kind: "professional",
                    _key: `prof-${row.id}`,
                    _title: row.test_name || `Тест #${row.test_id}`,
                })
            );

            const merged = [...psychItems, ...profItems].sort((a, b) => {
                const da = a.taken_at || a.created_at || "";
                const db = b.taken_at || b.created_at || "";
                return String(db).localeCompare(String(da));
            });
            setItems(merged);
        } catch (e) {
            showAlert(`Не удалось загрузить результаты: ${e.message || e}`, "error");
            setItems([]);
        } finally {
            setLoading(false);
        }
    }, [showAlert, typeFilter, appliedFio, appliedSpecialty]);

    useEffect(() => {
        load();
    }, [load]);

    const applyFilters = (e) => {
        e?.preventDefault?.();
        setAppliedFio(fioQuery.trim());
        setAppliedSpecialty(specialtyQuery.trim());
    };

    const specialties = useMemo(() => {
        const set = new Set();
        items.forEach((row) => {
            if (row.position) set.add(row.position);
        });
        return Array.from(set).sort((a, b) => a.localeCompare(b, "ru"));
    }, [items]);

    const openDetail = async (row) => {
        try {
            setDetailLoading(true);
            if (row._kind === "professional") {
                const full = await getPublicProfessionalResult(row.id);
                setSelected({ ...full, _kind: "professional" });
            } else {
                const full = await getPsychResult(row.id);
                setSelected({ ...full, _kind: "psychological" });
            }
        } catch (e) {
            showAlert(`Не удалось открыть результат: ${e.message || e}`, "error");
        } finally {
            setDetailLoading(false);
        }
    };

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <div className="mb-6 flex justify-between items-center gap-4 flex-wrap">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Результаты тестов</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        Психологические и профессиональные тесты (без привязки к карточке кандидата).
                    </p>
                </div>
                <button
                    type="button"
                    onClick={load}
                    disabled={loading}
                    className="text-sm px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 font-medium disabled:opacity-50"
                >
                    {loading ? "Обновление…" : "Обновить"}
                </button>
            </div>

            <form
                onSubmit={applyFilters}
                className="mb-4 bg-white rounded-2xl border border-slate-200/60 shadow-sm p-4 grid gap-3 md:grid-cols-4"
                data-testid="test-results-filters"
            >
                <label className="block text-sm">
                    <span className="text-slate-500">Тип теста</span>
                    <select
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-white"
                        value={typeFilter}
                        onChange={(e) => setTypeFilter(e.target.value)}
                        data-testid="filter-test-type"
                    >
                        <option value="all">Все</option>
                        <option value="psychological">Психологический</option>
                        <option value="professional">Профессиональный</option>
                    </select>
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Поиск по ФИО</span>
                    <input
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2"
                        value={fioQuery}
                        onChange={(e) => setFioQuery(e.target.value)}
                        placeholder="Иванов"
                        data-testid="filter-fio"
                    />
                </label>
                <label className="block text-sm">
                    <span className="text-slate-500">Специальность</span>
                    <input
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2"
                        value={specialtyQuery}
                        onChange={(e) => setSpecialtyQuery(e.target.value)}
                        placeholder="Логист"
                        list="test-results-specialty-list"
                        data-testid="filter-specialty"
                    />
                    <datalist id="test-results-specialty-list">
                        {specialties.map((s) => (
                            <option key={s} value={s} />
                        ))}
                    </datalist>
                </label>
                <div className="flex items-end">
                    <button
                        type="submit"
                        className="w-full text-sm px-4 py-2.5 rounded-xl bg-slate-900 text-white font-medium hover:bg-slate-800"
                        data-testid="filter-apply"
                    >
                        Применить
                    </button>
                </div>
            </form>

            <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm overflow-hidden">
                {loading && items.length === 0 ? (
                    <p className="p-8 text-slate-500 text-sm">Загрузка…</p>
                ) : items.length === 0 ? (
                    <p className="p-8 text-slate-500 text-sm">Результатов пока нет.</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-sm" data-testid="psych-results-table">
                            <thead className="bg-slate-50 text-slate-500 text-left">
                                <tr>
                                    <th className="px-4 py-3 font-medium">Дата</th>
                                    <th className="px-4 py-3 font-medium">Тип</th>
                                    <th className="px-4 py-3 font-medium">Тест</th>
                                    <th className="px-4 py-3 font-medium">ФИО</th>
                                    <th className="px-4 py-3 font-medium">Специальность</th>
                                    <th className="px-4 py-3 font-medium">Сводка</th>
                                    <th className="px-4 py-3 font-medium">ЧС / ЧМ</th>
                                    <th className="px-4 py-3 font-medium" />
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((row) => (
                                    <tr key={row._key} className="border-t border-slate-100 hover:bg-slate-50/50">
                                        <td className="px-4 py-3 text-slate-600">
                                            {row.taken_at
                                                ? new Date(row.taken_at).toLocaleDateString("ru-RU")
                                                : "—"}
                                        </td>
                                        <td className="px-4 py-3">
                                            <span
                                                className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                                                    row._kind === "psychological"
                                                        ? "bg-amber-50 text-amber-800 border-amber-100"
                                                        : "bg-blue-50 text-blue-800 border-blue-100"
                                                }`}
                                            >
                                                {typeLabel(row._kind)}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-slate-700 max-w-[220px] truncate" title={row._title}>
                                            {row._title}
                                        </td>
                                        <td className="px-4 py-3 font-medium text-slate-900">{row.full_name}</td>
                                        <td className="px-4 py-3 text-slate-600">{row.position}</td>
                                        <td className="px-4 py-3 text-slate-600">
                                            {row._kind === "psychological"
                                                ? (
                                                    <span className={
                                                        String(row.quality_status || "").includes("Критич")
                                                            ? "text-rose-700 font-semibold"
                                                            : ""
                                                    }>
                                                        {row.quality_status || "Результат готов"}
                                                    </span>
                                                )
                                                : profSummary(row)}
                                        </td>
                                        <td className="px-4 py-3 text-slate-600 tabular-nums">
                                            {row._kind === "psychological"
                                                ? (row.chs != null || row.chm != null
                                                    ? `ЧС ${row.chs ?? "—"} · ЧМ ${row.chm ?? "—"}`
                                                    : "—")
                                                : "—"}
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                type="button"
                                                onClick={() => openDetail(row)}
                                                className="text-sm font-medium text-[#3730a3] hover:underline"
                                            >
                                                {row._kind === "psychological" ? "Подробнее" : "Открыть"}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {(selected || detailLoading) && (
                <div
                    className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-start z-50 p-4 overflow-y-auto"
                    onClick={() => setSelected(null)}
                >
                    {detailLoading && !selected ? (
                        <div
                            className="bg-white rounded-2xl shadow-2xl w-full max-w-xl p-6 mt-10"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <p className="text-slate-500">Загрузка…</p>
                        </div>
                    ) : selected?._kind === "psychological" ? (
                        <div className="w-full max-w-[1368px] my-4" onClick={(e) => e.stopPropagation()}>
                            <PsychResultReport result={selected} onClose={() => setSelected(null)} />
                        </div>
                    ) : (
                        <ProfResultReport result={selected} onClose={() => setSelected(null)} />
                    )}
                </div>
            )}
        </MainLayout>
    );
}
