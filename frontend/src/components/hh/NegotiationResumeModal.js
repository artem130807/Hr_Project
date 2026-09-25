import CandidateProfileCard, { Chip } from "../candidates/CandidateProfileCard";

export default function NegotiationResumeModal({
    open,
    onClose,
    candidate,
    vacancyTitle,
    statusLabel,
    hhLink,
    alreadyCandidate,
    importing,
    onImport,
}) {
    if (!open || !candidate) return null;

    return (
        <div
            className="absolute inset-0 z-30 bg-slate-900/40 backdrop-blur-[2px] flex justify-center items-start sm:items-center p-3 sm:p-6"
            data-testid="negotiation-resume-modal"
            onClick={onClose}
        >
            <div
                className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-full sm:max-h-[90vh] flex flex-col overflow-hidden ring-1 ring-slate-900/5"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-slate-100 shrink-0">
                    <h2 className="text-lg font-bold text-slate-900">Карточка кандидата</h2>
                    <button
                        type="button"
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-colors"
                        aria-label="Закрыть"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div className="p-5 sm:p-6 overflow-y-auto flex-1">
                    <CandidateProfileCard
                        candidate={candidate}
                        vacancyTitle={vacancyTitle}
                        showAi={false}
                        aiHint="Оценка AI появится после добавления человека в кандидаты."
                        badges={(
                            <>
                                <Chip tone="sky">отклик HH</Chip>
                                {statusLabel ? <Chip>{statusLabel}</Chip> : null}
                            </>
                        )}
                        actions={(
                            <>
                                {hhLink ? (
                                    <a
                                        href={hhLink}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50"
                                    >
                                        Открыть резюме
                                    </a>
                                ) : null}
                                {alreadyCandidate ? (
                                    <span className="px-3.5 py-2 rounded-xl bg-slate-100 text-slate-600 text-sm font-medium">
                                        Уже в кандидатах
                                    </span>
                                ) : (
                                    <button
                                        type="button"
                                        onClick={onImport}
                                        disabled={importing}
                                        className="px-3.5 py-2 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold hover:bg-[#4338ca] disabled:opacity-50 shadow-sm"
                                    >
                                        {importing ? "Импорт..." : "В кандидаты"}
                                    </button>
                                )}
                            </>
                        )}
                    />
                </div>
            </div>
        </div>
    );
}
