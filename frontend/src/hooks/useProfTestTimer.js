import { useEffect, useRef, useState } from "react";

/**
 * Countdown timer for professional test take.
 * @param {number|null|undefined} durationMinutes
 * @param {{ enabled?: boolean, onExpire?: () => void }} options
 */
export function useProfTestTimer(durationMinutes, { enabled = false, onExpire } = {}) {
    const totalSeconds =
        durationMinutes != null && Number(durationMinutes) > 0
            ? Math.floor(Number(durationMinutes) * 60)
            : null;

    const [remainingSeconds, setRemainingSeconds] = useState(totalSeconds);
    const expiredRef = useRef(false);
    const onExpireRef = useRef(onExpire);

    useEffect(() => {
        onExpireRef.current = onExpire;
    }, [onExpire]);

    useEffect(() => {
        expiredRef.current = false;
        setRemainingSeconds(totalSeconds);
    }, [totalSeconds, enabled]);

    useEffect(() => {
        if (!enabled || totalSeconds == null) return undefined;

        const startedAt = Date.now();
        const tick = () => {
            const elapsed = Math.floor((Date.now() - startedAt) / 1000);
            const left = Math.max(0, totalSeconds - elapsed);
            setRemainingSeconds(left);
            if (left <= 0 && !expiredRef.current) {
                expiredRef.current = true;
                onExpireRef.current?.();
            }
        };
        tick();
        const id = window.setInterval(tick, 250);
        return () => window.clearInterval(id);
    }, [enabled, totalSeconds]);

    const mm = remainingSeconds != null ? Math.floor(remainingSeconds / 60) : null;
    const ss = remainingSeconds != null ? remainingSeconds % 60 : null;

    return {
        hasTimer: totalSeconds != null,
        remainingSeconds,
        formatted:
            mm != null
                ? `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`
                : null,
        isExpired: remainingSeconds === 0,
    };
}
