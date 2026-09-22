import React, {useEffect, useState} from "react";
import {getAutoSubscription, setAutoSubscription, isAuthorizedOnHH} from "../../services/hhSubscriptionApi";

/** Показать тумблер на странице кандидатов. Сейчас скрыт, логика сохранена. */
const AUTO_NEGOTIATIONS_TOGGLE_VISIBLE = false;

/**
 * Soft-fail HH auto-subscription errors so candidates page is usable without HH webhooks.
 */
export default function AutoNegotiationsToggle({className = "", onChanged}) {
    const [enabled, setEnabled] = useState(false)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState("")
    const authorized = isAuthorizedOnHH()

    useEffect(() => {
        if (!AUTO_NEGOTIATIONS_TOGGLE_VISIBLE) {
            setLoading(false)
            return undefined
        }
        let alive = true;
        (async () => {
            setLoading(true)
            setError("")
            try {
                const state = await getAutoSubscription()
                if(alive) setEnabled(state)
            } catch (e) {
                // Do not surface as a blocking red banner on candidates — HH service may be down.
                console.warn("HH auto-subscription status unavailable", e)
                if(alive) setEnabled(false)
            } finally {
                if(alive) setLoading(false)
            }
        })()
        return () => {alive = false}
    }, []);

    if (!AUTO_NEGOTIATIONS_TOGGLE_VISIBLE) {
        return null;
    }
    if (!authorized) return null

    const onToggle = async () => {
        setSaving(true)
        setError("")
        const next = !enabled
        try {
            await setAutoSubscription(next)
            setEnabled(next)
            onChanged && onChanged(next)
        } catch (e) {
            setEnabled(!next)
            setError("Ошибка обновления автообработки откликов")
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className={`flex items-center gap-3 ${className}`}>
            <span className="text-sm text-black">Автоматически обрабатывать отклики</span>

            <button
                type="button"
                onClick={onToggle}
                disabled={loading || saving}
                className={`
                    relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
                    transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[#e0bb48] focus:ring-offset-2 ${enabled ? "bg-[#e0bb48]" : "bg-[#666666]"}
                    ${loading || saving ? "opacity-60 cursor-not-allowed" : ""}
                `}
                aria-pressed={enabled}
            >
                <span className={`
                    pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${enabled ? "translate-x-5" : "translate-x-0"}
                `}/>
            </button>

            {loading && <span className="text-xs text-[#666666]">Загрузка...</span>}
            {saving && <span className="text-xs text-[#666666]">Сохранение</span>}
            {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
    )
}