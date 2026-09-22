import { CARD_STATUS_ACTIONS } from "../../utils/candidateStatuses";

const TONE_CLASS = {
    sky: "border-sky-200 text-sky-800 bg-sky-50 hover:bg-sky-100",
    amber: "border-amber-200 text-amber-900 bg-amber-50 hover:bg-amber-100",
    rose: "border-rose-200 text-rose-800 bg-rose-50 hover:bg-rose-100",
};

const TONE_ACTIVE = {
    sky: "bg-sky-700 text-white border-sky-700 hover:bg-sky-700",
    amber: "bg-amber-700 text-white border-amber-700 hover:bg-amber-700",
    rose: "bg-rose-700 text-white border-rose-700 hover:bg-rose-700",
};

export default function CandidateQuickActions({
    candidate,
    busy = false,
    isArchiveView = false,
    onStatus,
    onOffer,
    onInterview,
}) {
    const current = String(candidate?.status || "").trim();
    const offerSent = candidate?.offer_sent === true;

    if (isArchiveView) {
        return (
            <button
                type="button"
                onClick={(e) => {
                    e.stopPropagation();
                    onOffer?.(candidate);
                }}
                disabled={busy || offerSent}
                className="w-full px-3 py-2 rounded-xl text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
                {offerSent ? "Оффер уже отправлен" : "Отправить оффер"}
            </button>
        );
    }

    return (
        <div className="grid grid-cols-2 gap-2">
            {CARD_STATUS_ACTIONS.map((action) => {
                const active = current === action.status;
                return (
                    <button
                        key={action.status}
                        type="button"
                        title={action.label}
                        disabled={busy || active}
                        onClick={(e) => {
                            e.stopPropagation();
                            if (action.status === "собес") {
                                onInterview?.(candidate);
                                return;
                            }
                            onStatus?.(candidate, action.status);
                        }}
                        className={`px-3 py-2 rounded-xl text-xs sm:text-sm font-medium border transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                            active ? TONE_ACTIVE[action.tone] : TONE_CLASS[action.tone]
                        }`}
                    >
                        {action.label}
                    </button>
                );
            })}
            <button
                type="button"
                onClick={(e) => {
                    e.stopPropagation();
                    onOffer?.(candidate);
                }}
                disabled={busy || offerSent}
                className="px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
                {offerSent ? "Оффер отправлен" : "Отправить оффер"}
            </button>
        </div>
    );
}
