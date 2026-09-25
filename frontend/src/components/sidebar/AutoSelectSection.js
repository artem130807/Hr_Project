import { useState, useEffect } from "react";
import { getVacancies } from "../../services/vacancyApi";
import {
    getActiveAutosearches,
    getAvailableVacancies,
    activateAutosearch,
    deactivateAutosearch,
    setAutosearchInviteLimit,
} from "../../services/autosearchApi";
import { useAlertContext } from "../../context/AlertContext";

export default function AutoSelectSection() {
    const [activeSearches, setActiveSearches] = useState([]);
    const [availableVacancies, setAvailableVacancies] = useState([]);
    const [vacancyMap, setVacancyMap] = useState({});
    const [expandedId, setExpandedId] = useState(null);
    const [inviteLimits, setInviteLimits] = useState({});
    const [savingLimit, setSavingLimit] = useState({});
    const [activatingId, setActivatingId] = useState(null);
    const [selectedToActivate, setSelectedToActivate] = useState("");
    const { showAlert } = useAlertContext();

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [allVacancies, active, available] = await Promise.all([
                getVacancies(),
                getActiveAutosearches(),
                getAvailableVacancies().catch(() => []),
            ]);

            const map = {};
            if (Array.isArray(allVacancies)) {
                allVacancies.forEach(v => { map[v.id] = v.name || v.title || `Вакансия #${v.id}`; });
            }
            setVacancyMap(map);

            setActiveSearches(Array.isArray(active) ? active : []);
            setAvailableVacancies(Array.isArray(available) ? available : []);
            const limits = {};
            if (Array.isArray(active)) {
                active.forEach(s => { limits[s.vacancy_id] = s.invite_limit; });
            }
            setInviteLimits(limits);
        } catch (e) {
            console.error("Ошибка загрузки данных автоподбора:", e);
            setActiveSearches([]);
            setAvailableVacancies([]);
        }
    };

    const toggleExpanded = (id) => setExpandedId(expandedId === id ? null : id);

    const handleActivate = async () => {
        const vacancyId = Number(selectedToActivate);
        if (!Number.isFinite(vacancyId) || vacancyId <= 0) {
            showAlert("Выберите вакансию для автоподбора", "warning");
            return;
        }
        try {
            setActivatingId(vacancyId);
            await activateAutosearch(vacancyId);
            showAlert("Автоподбор запущен", "success");
            setSelectedToActivate("");
            await loadData();
        } catch (e) {
            showAlert(`Не удалось запустить автоподбор: ${e.message}`, "error");
        } finally {
            setActivatingId(null);
        }
    };

    const handleStop = async (search) => {
        if (!window.confirm(`Остановить автоподбор для "${vacancyMap[search.vacancy_id] || search.vacancy_id}"?`)) return;
        try {
            await deactivateAutosearch(search.vacancy_id);
            setActiveSearches(prev => prev.filter(s => s.vacancy_id !== search.vacancy_id));
            showAlert("Автоподбор остановлен", "success");
            await loadData();
        } catch (e) {
            console.error(e);
            showAlert("Ошибка остановки автоподбора", "error");
        }
    };

    const handleSaveLimit = async (id) => {
        try {
            setSavingLimit(prev => ({ ...prev, [id]: true }));
            await setAutosearchInviteLimit(id, Number(inviteLimits[id]));
            showAlert("Лимит обновлён", "success");
        } catch {
            showAlert("Ошибка обновления лимита", "error");
        } finally {
            setSavingLimit(prev => ({ ...prev, [id]: false }));
        }
    };

    return (
        <div className="mt-4">
            <h3 className="text-sm font-semibold mb-2">Автоподбор</h3>

            <div className="mb-3 space-y-2">
                <select
                    className="w-full border rounded px-2 py-1 text-sm"
                    value={selectedToActivate}
                    onChange={(e) => setSelectedToActivate(e.target.value)}
                >
                    <option value="">Запустить для вакансии…</option>
                    {availableVacancies.map((v) => (
                        <option key={v.id} value={v.id}>
                            {v.name || vacancyMap[v.id] || `Вакансия #${v.id}`}
                        </option>
                    ))}
                </select>
                <button
                    type="button"
                    className="w-full px-2 py-1 bg-[#4f46e5] text-white rounded text-xs font-medium disabled:opacity-50"
                    onClick={handleActivate}
                    disabled={!!activatingId || !selectedToActivate}
                >
                    {activatingId ? "Запуск…" : "Запустить автоподбор"}
                </button>
                {availableVacancies.length === 0 && (
                    <p className="text-xs text-gray-500">
                        Нет доступных вакансий (нужна публикация на HH.ru)
                    </p>
                )}
            </div>

            {activeSearches.length === 0 ? (
                <div className="text-gray-500 text-sm">Нет активных автоподборов</div>
            ) : (
                <div className="space-y-1">
                    {activeSearches.map(search => (
                        <div key={search.vacancy_id} className="border rounded p-2 bg-white">
                            <div
                                className="flex justify-between items-center cursor-pointer"
                                onClick={() => toggleExpanded(search.vacancy_id)}
                            >
                                <span className="font-medium text-sm truncate">{vacancyMap[search.vacancy_id]}</span>
                                <span>{expandedId === search.vacancy_id ? "▲" : "▼"}</span>
                            </div>
                            {expandedId === search.vacancy_id && (
                                <div className="mt-2 text-sm text-gray-700 space-y-1">
                                    <div>Всего отправлено: {search.total_sent}</div>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="number"
                                            min="1"
                                            className="border rounded px-1 w-20"
                                            value={inviteLimits[search.vacancy_id] ?? ""}
                                            onChange={e => setInviteLimits(prev => ({ ...prev, [search.vacancy_id]: e.target.value }))}
                                            disabled={savingLimit[search.vacancy_id]}
                                        />
                                        <button
                                            className="px-2 py-1 bg-yellow-400 rounded text-xs"
                                            onClick={() => handleSaveLimit(search.vacancy_id)}
                                            disabled={savingLimit[search.vacancy_id]}
                                        >
                                            {savingLimit[search.vacancy_id] ? "Сохр..." : "Сохранить"}
                                        </button>
                                    </div>
                                    <button
                                        className="px-2 py-1 bg-gray-500 text-white rounded text-xs"
                                        onClick={() => handleStop(search)}
                                    >
                                        Стоп
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
