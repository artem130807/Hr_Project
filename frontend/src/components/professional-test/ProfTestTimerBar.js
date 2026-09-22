export default function ProfTestTimerBar({ formatted, remainingSeconds, totalSeconds }) {
    if (!formatted) return null;
    const urgent = remainingSeconds != null && remainingSeconds <= 60;
    const ratio =
        totalSeconds > 0 && remainingSeconds != null
            ? Math.max(0, Math.min(1, remainingSeconds / totalSeconds))
            : 1;

    return (
        <div
            className={`sticky top-0 z-20 backdrop-blur border-b ${
                urgent ? "bg-rose-50/95 border-rose-200" : "bg-white/90 border-slate-200"
            }`}
            data-testid="prof-timer"
        >
            <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Осталось времени
                </span>
                <span
                    className={`font-mono text-lg font-bold tabular-nums ${
                        urgent ? "text-rose-700" : "text-slate-900"
                    }`}
                >
                    {formatted}
                </span>
            </div>
            <div className="h-1 bg-slate-100">
                <div
                    className={`h-full transition-[width] duration-300 ${
                        urgent ? "bg-rose-500" : "bg-[#cda834]"
                    }`}
                    style={{ width: `${ratio * 100}%` }}
                />
            </div>
        </div>
    );
}
