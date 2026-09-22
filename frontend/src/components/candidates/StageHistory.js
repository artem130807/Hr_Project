import { useEffect, useState, useCallback } from "react";
import { getCandidateStageHistory } from "../../services/hrOpsApi";
import { useAlertContext } from "../../context/AlertContext";

export default function StageHistory({ candidateId }) {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const { showAlert } = useAlertContext();

    const fetchHistory = useCallback(async () => {
        if (!candidateId) return;
        try {
            setLoading(true);
            const data = await getCandidateStageHistory(candidateId);
            setHistory(Array.isArray(data) ? data : []);
        } catch (error) {
            showAlert("Ошибка загрузки истории: " + (error.message || error), "error");
            setHistory([]);
        } finally {
            setLoading(false);
        }
    }, [candidateId, showAlert]);

    useEffect(() => {
        fetchHistory();
    }, [fetchHistory]);

    return (
        <div className="bg-white p-4 rounded-xl border border-slate-200/60 shadow-sm mt-6">
            <h3 className="font-semibold text-lg mb-2 text-slate-900">История этапов</h3>
            {loading ? (
                <p className="text-sm text-slate-400">Загрузка...</p>
            ) : history.length === 0 ? (
                <p className="text-sm text-slate-400">История пока пуста.</p>
            ) : (
                <ul className="text-sm space-y-2">
                    {history.map((step) => (
                        <li key={step.id} className="border-b border-slate-100 pb-2">
                            <div className="font-medium text-slate-800">
                                {step.to_status || step.to_stage || "—"}
                                {(step.from_status || step.from_stage) && (
                                    <span className="text-slate-400 font-normal">
                                        {" "}← {step.from_status || step.from_stage}
                                    </span>
                                )}
                            </div>
                            {step.comment && <div className="text-slate-600">{step.comment}</div>}
                            <div className="text-xs text-slate-400">
                                {step.actor_name ? `${step.actor_name} · ` : ""}
                                {step.created_at ? new Date(step.created_at).toLocaleString("ru-RU") : ""}
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
