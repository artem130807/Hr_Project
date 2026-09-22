import { useEffect, useState } from "react";
import { listPsychInstruments } from "../../services/psychTestApi";
import { psychPublicTakePath } from "../../config/navConfig";
import { useAlertContext } from "../../context/AlertContext";

export default function PsychInstrumentCatalog() {
    const { showAlert } = useAlertContext();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [copiedId, setCopiedId] = useState(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                setLoading(true);
                const data = await listPsychInstruments();
                const list = Array.isArray(data) ? data : data?.items || [];
                if (!cancelled) setItems(list);
            } catch (e) {
                if (!cancelled) {
                    showAlert(`Не удалось загрузить психологические тесты: ${e.message || e}`, "error");
                    setItems([]);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const copyLink = async (instrumentId) => {
        const path = psychPublicTakePath(instrumentId);
        const url = `${window.location.origin}${path}`;
        try {
            await navigator.clipboard.writeText(url);
            setCopiedId(instrumentId);
            showAlert("Ссылка скопирована", "success");
            setTimeout(() => setCopiedId(null), 2000);
        } catch {
            showAlert(`Скопируйте вручную: ${url}`, "warning");
        }
    };

    if (loading) {
        return <p className="text-sm text-slate-500 py-4">Загрузка готовых психологических тестов…</p>;
    }

    if (!items.length) {
        return <p className="text-slate-500 text-sm italic py-4">Готовые психологические тесты пока не подключены.</p>;
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="psych-instrument-catalog">
            {items.map((inst) => (
                <div
                    key={inst.id}
                    className="bg-white rounded-2xl shadow-sm border border-slate-200/60 hover:shadow-md transition-shadow flex flex-col overflow-hidden"
                >
                    <div className="p-6 flex-1">
                        <div className="flex justify-between items-start gap-3 mb-3">
                            <h3 className="text-lg font-bold text-slate-900 leading-tight">{inst.name}</h3>
                            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-700 flex items-center justify-center shrink-0">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-2 mb-3">
                            <span className="px-2 py-1 bg-slate-50 text-slate-600 border border-slate-200/60 rounded text-[10px] font-bold uppercase tracking-wider">
                                Психологический тест
                            </span>
                            {inst.version && (
                                <span className="px-2 py-1 bg-slate-50 text-slate-600 border border-slate-200/60 rounded text-[10px] font-bold uppercase tracking-wider">
                                    v{inst.version}
                                </span>
                            )}
                            {inst.item_count != null && (
                                <span className="px-2 py-1 bg-slate-50 text-slate-600 border border-slate-200/60 rounded text-[10px] font-bold uppercase tracking-wider">
                                    {inst.item_count} пунктов
                                </span>
                            )}
                        </div>
                        {inst.description && (
                            <p className="text-sm text-slate-500 line-clamp-4">{inst.description}</p>
                        )}
                        {inst.duration_minutes && (
                            <p className="text-xs text-slate-400 mt-3">Время: ~{inst.duration_minutes} мин.</p>
                        )}
                    </div>
                    <div className="p-4 border-t border-slate-100 bg-slate-50/50 flex flex-col gap-2">
                        <button
                            type="button"
                            data-testid={`copy-psych-link-${inst.id}`}
                            onClick={() => copyLink(inst.id)}
                            className="w-full text-sm px-4 py-2.5 rounded-xl bg-slate-900 text-white hover:bg-slate-800 font-medium"
                        >
                            {copiedId === inst.id ? "Скопировано" : "Скопировать ссылку для прохождения"}
                        </button>
                        <a
                            href={psychPublicTakePath(inst.id)}
                            target="_blank"
                            rel="noreferrer"
                            className="text-center text-sm text-slate-600 hover:text-slate-900"
                        >
                            Открыть страницу теста
                        </a>
                    </div>
                </div>
            ))}
        </div>
    );
}
