import { useEffect, useState, useCallback } from "react";
import dayjs from "dayjs";
import MainLayout from "../layout/MainLayout";
import FunnelChart from "../components/analytics/FunnelChart";
import AnalyticsTable from "../components/analytics/AnalyticsTable";
import { getActiveCandidates, exportAnalyticsTable } from "../services/analyticsApi";
import { getVacancyOptions } from "../services/vacancyApi";
import { useAlertContext } from "../context/AlertContext";
import { buildCandidateFunnelRows, totalFunnelCount } from "../utils/candidateAnalytics";

export default function AnalyticsPage() {
    const [data, setData] = useState([]);
    const [dateRange, setDateRange] = useState({
        from: dayjs().startOf("month").format("YYYY-MM-DD"),
        to: dayjs().endOf("month").format("YYYY-MM-DD"),
    });
    const { showAlert } = useAlertContext();
    const [loading, setLoading] = useState(true);
    const [vacancies, setVacancies] = useState([]);
    const [selectedVacancyId, setSelectedVacancyId] = useState("");
    const [vacanciesLoading, setVacanciesLoading] = useState(false);

    const fetchAnalytics = useCallback(async () => {
        try {
            setLoading(true);
            const payload = await getActiveCandidates(selectedVacancyId || null);
            setData(buildCandidateFunnelRows(payload?.stats));
        } catch (e) {
            console.error("Ошибка загрузки аналитики: ", e);
            setData(buildCandidateFunnelRows({}));
            showAlert(`Ошибка загрузки статистики: ${e.message || e}`, "error");
        } finally {
            setLoading(false);
        }
    }, [selectedVacancyId, showAlert]);

    useEffect(() => {
        fetchAnalytics();
    }, [fetchAnalytics]);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                setVacanciesLoading(true);
                const list = await getVacancyOptions();
                if (!cancelled) {
                    setVacancies(Array.isArray(list) ? list : []);
                }
            } catch (e) {
                if (!cancelled) {
                    setVacancies([]);
                    showAlert(`Ошибка загрузки вакансий: ${e.message || e}`, "error");
                }
            } finally {
                if (!cancelled) setVacanciesLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [showAlert]);

    const handleExport = async () => {
        try {
            await exportAnalyticsTable(dateRange.from, dateRange.to, selectedVacancyId || null);
        } catch (e) {
            console.error(e);
            showAlert(String(e.message || e), "error");
        }
    };

    const total = totalFunnelCount(data);

    return (
        <MainLayout className="p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-900" data-testid="analytics-page-title">
                    Статистика кандидатов
                </h1>
                <p className="mt-1 text-sm text-slate-500">
                    Воронка по актуальным статусам найма
                </p>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-6 mb-6 shadow-sm">
                <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
                    <h2 className="text-lg font-semibold text-slate-900">Сводка по статусам</h2>
                    <p className="text-sm text-slate-500" data-testid="analytics-total">
                        Всего кандидатов: <span className="font-semibold text-slate-800">{total}</span>
                    </p>
                </div>

                {loading ? (
                    <p className="text-slate-500 text-sm">Загрузка…</p>
                ) : data.length > 0 ? (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="analytics-status-cards">
                        {data.map((row) => (
                            <div
                                key={row.name}
                                className={`rounded-xl border px-4 py-3 ${
                                    row.count > 0
                                        ? "bg-[#4f46e5]/10 border-[#4f46e5]/30"
                                        : "bg-slate-50 border-slate-100"
                                }`}
                                style={{ marginLeft: Math.min(row.depth, 3) * 8 }}
                            >
                                <div className="text-xs text-slate-500 mb-1 truncate" title={row.name}>
                                    {row.hasChildren ? "▾ " : "• "}
                                    {row.name}
                                </div>
                                <div className="text-2xl font-bold text-slate-900">{row.count}</div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-slate-500">Нет данных</p>
                )}
            </div>

            <div className="flex items-center gap-4 mb-4 flex-wrap">
                <label className="text-sm text-slate-600">
                    От:
                    <input
                        type="date"
                        value={dateRange.from}
                        onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })}
                        className="ml-2 border border-slate-200 rounded-lg px-2 py-1.5"
                        data-testid="analytics-date-from"
                    />
                </label>
                <label className="text-sm text-slate-600">
                    До:
                    <input
                        type="date"
                        value={dateRange.to}
                        onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })}
                        className="ml-2 border border-slate-200 rounded-lg px-2 py-1.5"
                        data-testid="analytics-date-to"
                    />
                </label>
                <label className="text-sm text-slate-600">
                    Вакансия:
                    <select
                        value={selectedVacancyId}
                        onChange={(e) => setSelectedVacancyId(e.target.value)}
                        className="ml-2 border border-slate-200 rounded-lg px-2 py-1.5 bg-white min-w-[220px]"
                        data-testid="analytics-vacancy-select"
                        disabled={vacanciesLoading}
                    >
                        <option value="">Все вакансии</option>
                        {vacancies.map((vacancy) => (
                            <option key={vacancy.id} value={vacancy.id}>
                                {vacancy.name || `Вакансия #${vacancy.id}`}
                            </option>
                        ))}
                    </select>
                </label>
                <button
                    type="button"
                    onClick={handleExport}
                    className="bg-slate-900 text-white font-medium px-4 py-2 rounded-xl hover:bg-slate-800 text-sm"
                    data-testid="analytics-export"
                >
                    Скачать Excel по периоду
                </button>
                <button
                    type="button"
                    onClick={fetchAnalytics}
                    className="border border-slate-200 bg-white text-slate-700 font-medium px-4 py-2 rounded-xl hover:bg-slate-50 text-sm"
                >
                    Обновить
                </button>
            </div>

            <FunnelChart data={data} />
            <AnalyticsTable data={data} />
        </MainLayout>
    );
}
