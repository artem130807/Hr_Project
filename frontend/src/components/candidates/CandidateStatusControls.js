import { useState, useEffect } from "react";
import { applyCandidateStatus, getCandidatesStatuses, sendOffer } from "../../services/candidateApi";
import { useAlertContext } from "../../context/AlertContext";
import OfferModal from "./OfferModal";
import CandidateStatusTree from "./CandidateStatusTree";
import { buildOfferLetterText } from "../../utils/interviewInvite";
import { allowedStatusTransitions, statusNextAction, statusStage, statusState } from "../../utils/candidateStatuses";

export default function CandidateStatusControls({ candidate, onChange, showOffer = true }) {
    const [loading, setLoading] = useState(false);
    const [currentStatus, setCurrentStatus] = useState(null);
    const { showAlert } = useAlertContext();
    const [statuses, setStatuses] = useState([]);
    const [offerOpen, setOfferOpen] = useState(false);
    const allowed = allowedStatusTransitions(currentStatus, statuses);

    useEffect(() => {
        if (!candidate) return;
        setCurrentStatus(candidate?.status ?? candidate?.status_code ?? candidate?.status_name ?? null);
    }, [candidate?.id, candidate?.status, candidate?.status_code, candidate?.status_name, candidate]);

    useEffect(() => {
        const loadStatuses = async () => {
            try {
                const list = await getCandidatesStatuses();
                setStatuses(list);
            } catch (e) {
                setStatuses([]);
            }
        };
        loadStatuses();
    }, []);

    const handleStatusChange = async (newStatus) => {
        try {
            setLoading(true);
            await applyCandidateStatus(candidate.id, newStatus);
            setCurrentStatus(newStatus);
            showAlert("Статус обновлен", "success");
            onChange?.();
        } catch (e) {
            const message = e?.message || "Не удалось обновить статус";
            showAlert(`Ошибка: ${message}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const handleOfferSubmit = async (offerText, includeDocumentsLink = false) => {
        try {
            setLoading(true);
            await sendOffer(candidate.id, offerText, includeDocumentsLink);
            showAlert("Оффер отправлен", "success");
            setOfferOpen(false);
            onChange?.();
        } catch (e) {
            showAlert(`Ошибка отправки оффера: ${e.message}`, "error");
        } finally {
            setLoading(false);
        }
    };

    if (!candidate) {
        return <div className="text-gray-500 text-sm">Кандидат не выбран</div>;
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-3" data-testid="candidate-status-summary">
                <div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-500">Текущий этап</div><div className="font-semibold">{statusStage(currentStatus, statuses)}</div></div>
                <div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-500">Состояние</div><div className="font-semibold">{statusState(currentStatus, candidate.stage, statuses)}</div></div>
                <div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-500">Ближайшее действие</div><div className="font-semibold">{statusNextAction(currentStatus, statuses)}</div></div>
            </div>
            <h3 className="text-sm font-semibold text-slate-700">Доступные переходы</h3>

            <CandidateStatusTree
                currentStatus={currentStatus ?? candidate?.status}
                statusesFromApi={statuses}
                disabled={loading || !candidate?.id}
                allowedTransitions={allowed}
                onSelect={(value) => candidate?.id && handleStatusChange(value)}
            />

            {showOffer ? (
            <div className="flex gap-4">
                <button
                    type="button"
                    disabled={candidate?.offer_sent || loading}
                    onClick={() => setOfferOpen(true)}
                    className={`px-3 py-1 rounded text-sm ${
                        candidate?.offer_sent
                            ? "bg-green-200 text-gray-600"
                            : "bg-green-600 text-white"
                    }`}
                >
                    {candidate?.offer_sent ? "Оффер отправлен" : "Отправить оффер"}
                </button>
            </div>
            ) : null}

            <OfferModal
                open={offerOpen}
                onClose={() => setOfferOpen(false)}
                onSubmit={handleOfferSubmit}
                defaultText={buildOfferLetterText(candidate.full_name, `Здравствуйте, ${candidate.full_name || ""}!\n\nМы готовы сделать вам предложение о работе.`)}
            />
        </div>
    );
}
