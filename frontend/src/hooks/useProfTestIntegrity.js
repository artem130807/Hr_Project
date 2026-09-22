import { useCallback, useEffect, useRef, useState } from "react";

const BLUR_COALESCE_MS = 400;

/**
 * Integrity monitoring for professional test take:
 * - tab / window blur → onTabBlur (coalesced so visibility+blur count once)
 * - mouse leave of the question zone → onMouseLeave
 *
 * Callbacks may return `false` to skip incrementing counters
 * (e.g. question already locked).
 */
export function useProfTestIntegrity({
    enabled = false,
    onTabBlur,
    onMouseLeave,
} = {}) {
    const [tabBlurCount, setTabBlurCount] = useState(0);
    const [mouseLeaveCount, setMouseLeaveCount] = useState(0);
    const zoneRef = useRef(null);
    const enabledRef = useRef(enabled);
    const onTabBlurRef = useRef(onTabBlur);
    const onMouseLeaveRef = useRef(onMouseLeave);
    const lastBlurAtRef = useRef(0);

    useEffect(() => {
        enabledRef.current = enabled;
    }, [enabled]);

    useEffect(() => {
        onTabBlurRef.current = onTabBlur;
        onMouseLeaveRef.current = onMouseLeave;
    }, [onTabBlur, onMouseLeave]);

    useEffect(() => {
        if (!enabled) return undefined;

        const fireTabBlur = () => {
            if (!enabledRef.current) return;
            const now = Date.now();
            if (now - lastBlurAtRef.current < BLUR_COALESCE_MS) return;
            lastBlurAtRef.current = now;
            const accepted = onTabBlurRef.current?.();
            if (accepted === false) return;
            setTabBlurCount((c) => c + 1);
        };

        const handleVisibility = () => {
            if (document.visibilityState === "hidden") {
                fireTabBlur();
            }
        };
        const handleWindowBlur = () => {
            if (document.hasFocus()) return;
            fireTabBlur();
        };

        document.addEventListener("visibilitychange", handleVisibility);
        window.addEventListener("blur", handleWindowBlur);
        return () => {
            document.removeEventListener("visibilitychange", handleVisibility);
            window.removeEventListener("blur", handleWindowBlur);
        };
    }, [enabled]);

    const handleZoneMouseLeave = useCallback(() => {
        if (!enabledRef.current) return;
        const accepted = onMouseLeaveRef.current?.();
        if (accepted === false) return;
        setMouseLeaveCount((c) => c + 1);
    }, []);

    return {
        zoneRef,
        tabBlurCount,
        mouseLeaveCount,
        handleZoneMouseLeave,
        resetCounters: () => {
            setTabBlurCount(0);
            setMouseLeaveCount(0);
            lastBlurAtRef.current = 0;
        },
    };
}
