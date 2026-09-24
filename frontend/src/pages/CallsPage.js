import { useEffect, useMemo, useRef, useState } from "react";
import MainLayout from "../layout/MainLayout";
import { CALL_OUTCOMES, CALL_DIRECTIONS } from "../data/callOutcomes";
import { getCallConversations } from "../services/callsApi";
import { canonicalRuPhone, formatRuPhone, isPhoneQuery } from "../utils/phoneSearch";
import { mapCallConversations } from "../utils/callConversationView";
import { filterCalls, formatCallDuration } from "../utils/callFilters";
import { useAlertContext } from "../context/AlertContext";
import T2AtsConnectPanel from "../components/calls/T2AtsConnectPanel";

function formatWhen(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function speakerMeta(speaker) {
    if (speaker === "hr") return { name: "HR", bubble: "bg-white border-slate-200 text-slate-800", align: "items-start" };
    if (speaker === "system") return { name: "Система", bubble: "bg-slate-100 border-slate-200 text-slate-500 italic", align: "items-center" };
    return { name: "Собеседник", bubble: "bg-[#4f46e5]/10 border-[#4f46e5]/20 text-slate-900", align: "items-end" };
}

function highlightText(text, query) {
    const q = String(query || "").trim();
    if (!q) return text;
    const lower = text.toLowerCase();
    const needle = q.toLowerCase();
    const parts = [];
    let i = 0;
    while (i < text.length) {
        const at = lower.indexOf(needle, i);
        if (at === -1) {
            parts.push(text.slice(i));
            break;
        }
        if (at > i) parts.push(text.slice(i, at));
        parts.push(
            <mark key={`${at}-${i}`} className="bg-[#4f46e5]/40 text-slate-900 rounded px-0.5">
                {text.slice(at, at + q.length)}
            </mark>
        );
        i = at + q.length;
    }
    return parts;
}

export default function CallsPage() {
    const { showAlert } = useAlertContext();
    const showAlertRef = useRef(showAlert);
    const [calls, setCalls] = useState([]);
    const [loading, setLoading] = useState(true);
    const [phoneQuery, setPhoneQuery] = useState("");
    const [direction, setDirection] = useState("all");
    const [outcome, setOutcome] = useState("all");
    const [selectedId, setSelectedId] = useState(null);
    const [inTranscript, setInTranscript] = useState("");

    useEffect(() => {
        showAlertRef.current = showAlert;
    }, [showAlert]);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            try {
                const payload = await getCallConversations({ limit: 500 });
                if (cancelled) return;
                const mapped = mapCallConversations(payload);
                setCalls(mapped);
                setSelectedId((current) => current ?? mapped[0]?.id ?? null);
            } catch (err) {
                if (!cancelled) {
                    setCalls([]);
                    showAlertRef.current?.(err?.message || "Не удалось загрузить звонки", "error");
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    const filtered = useMemo(
        () =>
            filterCalls(calls, { phoneQuery, direction, outcome }).slice().sort(
                (a, b) => new Date(b.startedAt) - new Date(a.startedAt)
            ),
        [calls, phoneQuery, direction, outcome]
    );

    const selected = filtered.find((c) => c.id === selectedId) || filtered[0] || null;

    const stats = useMemo(() => {
        const unique = new Set(filtered.map((c) => canonicalRuPhone(c.phone)));
        const totalSec = filtered.reduce((s, c) => s + (c.durationSec || 0), 0);
        return {
            count: filtered.length,
            unique: unique.size,
            avg: filtered.length ? Math.round(totalSec / filtered.length) : 0,
        };
    }, [filtered]);

    const phoneReady = isPhoneQuery(phoneQuery);

    return (
        <MainLayout className="flex flex-col h-full min-h-0">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Звонки</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        Записи из АТС t2 с участием линии +7 902 001-37-28 (звонящий или оператор).
                        Поиск внутри этого списка — по номеру.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                    <span className="px-3 py-1.5 rounded-full bg-white border border-slate-200 text-slate-600">
                        {stats.count} звонков
                    </span>
                    <span className="px-3 py-1.5 rounded-full bg-white border border-slate-200 text-slate-600">
                        {stats.unique} номеров
                    </span>
                    <span className="px-3 py-1.5 rounded-full bg-white border border-slate-200 text-slate-600">
                        среднее {formatCallDuration(stats.avg)}
                    </span>
                </div>
            </div>

            <T2AtsConnectPanel />

            <label className="block mb-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Поиск по номеру
                </span>
                <div className="mt-1.5 relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.13.96.36 1.9.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0122 16.92z" />
                        </svg>
                    </span>
                    <input
                        type="tel"
                        inputMode="tel"
                        autoComplete="tel"
                        placeholder="+7 999 123-45-67"
                        value={phoneQuery}
                        onChange={(e) => setPhoneQuery(e.target.value)}
                        data-testid="calls-phone-search"
                        className="w-full h-12 pl-12 pr-28 rounded-2xl border border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 shadow-sm focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/40 focus:border-[#4f46e5]"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-slate-400">
                        {phoneReady ? "точное совпадение" : "от 4 цифр"}
                    </span>
                </div>
            </label>

            <div className="flex flex-wrap gap-2 mb-4">
                <select
                    value={direction}
                    onChange={(e) => setDirection(e.target.value)}
                    data-testid="calls-direction-filter"
                    className="h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-700"
                >
                    <option value="all">Все направления</option>
                    <option value="incoming">Входящие</option>
                    <option value="outgoing">Исходящие</option>
                </select>
                <select
                    value={outcome}
                    onChange={(e) => setOutcome(e.target.value)}
                    className="h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-700"
                >
                    <option value="all">Все итоги</option>
                    {Object.entries(CALL_OUTCOMES).map(([key, meta]) => (
                        <option key={key} value={key}>{meta.label}</option>
                    ))}
                </select>
                {phoneQuery && (
                    <button
                        type="button"
                        onClick={() => setPhoneQuery("")}
                        className="h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-600 hover:bg-slate-50"
                    >
                        Сбросить номер
                    </button>
                )}
            </div>

            <div className="grid lg:grid-cols-[minmax(280px,380px)_1fr] gap-4 min-h-0 flex-1">
                <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden flex flex-col max-h-[calc(100vh-280px)]">
                    <div className="px-4 py-3 border-b border-slate-100 text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Список записей
                    </div>
                    <div className="overflow-y-auto flex-1" data-testid="calls-list">
                        {loading ? (
                            <p className="p-6 text-sm text-slate-500">Загрузка записей…</p>
                        ) : filtered.length === 0 ? (
                            <p className="p-6 text-sm text-slate-500">
                                {phoneReady
                                    ? "Нет звонков с таким номером."
                                    : "Нет записей. Они появятся после синхронизации с АТС t2."}
                            </p>
                        ) : (
                            filtered.map((call) => {
                                const active = selected?.id === call.id;
                                const outcomeMeta = CALL_OUTCOMES[call.outcome] || CALL_OUTCOMES.pending;
                                return (
                                    <button
                                        key={call.id}
                                        type="button"
                                        onClick={() => {
                                            setSelectedId(call.id);
                                            setInTranscript("");
                                        }}
                                        data-testid={`call-row-${call.id}`}
                                        className={`w-full text-left px-4 py-3.5 border-b border-slate-100 transition-colors ${
                                            active ? "bg-[#4f46e5]/10" : "hover:bg-slate-50"
                                        }`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div>
                                                <div className="font-semibold text-slate-900 tabular-nums">
                                                    {formatRuPhone(call.phone)}
                                                </div>
                                                <div className="text-sm text-slate-600 mt-0.5">{call.contactName}</div>
                                            </div>
                                            <span className="text-[11px] text-slate-400 whitespace-nowrap">
                                                {formatWhen(call.startedAt)}
                                            </span>
                                        </div>
                                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
                                                {CALL_DIRECTIONS[call.direction]?.short}
                                            </span>
                                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${outcomeMeta.className}`}>
                                                {outcomeMeta.label}
                                            </span>
                                            <span className="text-[11px] text-slate-400">{formatCallDuration(call.durationSec)}</span>
                                        </div>
                                    </button>
                                );
                            })
                        )}
                    </div>
                </div>

                <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden flex flex-col max-h-[calc(100vh-280px)] min-h-[420px]">
                    {!selected ? (
                        <div className="flex-1 grid place-items-center text-slate-400 text-sm p-8">
                            {loading
                                ? "Загрузка…"
                                : "Выберите звонок слева, чтобы открыть расшифровку."}
                        </div>
                    ) : (
                        <>
                            <header className="px-5 py-4 border-b border-slate-100">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                                            {selected.recordingName || "Запись"}
                                        </div>
                                        <h2 className="text-xl font-bold text-slate-900">{selected.contactName}</h2>
                                        <p className="mt-1 text-sm tabular-nums text-slate-600" data-testid="call-detail-phone">
                                            {formatRuPhone(selected.phone)}
                                            <button
                                                type="button"
                                                className="ml-2 text-[11px] font-semibold uppercase tracking-wide text-[#9a7d18] hover:underline"
                                                onClick={() => navigator.clipboard?.writeText(formatRuPhone(selected.phone))}
                                            >
                                                копировать
                                            </button>
                                        </p>
                                    </div>
                                    <div className="text-right text-sm text-slate-500">
                                        <div>{formatWhen(selected.startedAt)}</div>
                                        <div className="mt-1">{formatCallDuration(selected.durationSec)} · {CALL_DIRECTIONS[selected.direction]?.label}</div>
                                    </div>
                                </div>
                                <p className="mt-3 text-sm text-slate-600 leading-relaxed">{selected.summary}</p>
                                <div className="mt-3 flex items-center gap-2 text-xs text-slate-400 bg-slate-50 border border-slate-100 rounded-xl px-3 py-2">
                                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19V6l12-2v13M9 19c0 1.1-1.8 2-4 2s-4-.9-4-2 1.8-2 4-2 4 .9 4 2zm12-3c0 1.1-1.8 2-4 2s-4-.9-4-2 1.8-2 4-2 4 .9 4 2z" />
                                    </svg>
                                    Расшифровка записи · {selected.recordingName}
                                </div>
                            </header>
                            <div className="px-5 py-3 border-b border-slate-100">
                                <input
                                    type="search"
                                    placeholder="Найти в расшифровке…"
                                    value={inTranscript}
                                    onChange={(e) => setInTranscript(e.target.value)}
                                    className="w-full h-10 px-3 rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/40 focus:bg-white"
                                />
                            </div>
                            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3" data-testid="call-transcript">
                                {(!selected.turns || selected.turns.length === 0) ? (
                                    <p className="text-sm text-slate-500">Расшифровка пока недоступна.</p>
                                ) : selected.turns.map((turn, idx) => {
                                    const meta = speakerMeta(turn.speaker);
                                    return (
                                        <div key={`${selected.id}-${idx}`} className={`flex flex-col ${meta.align}`}>
                                            <div className={`max-w-[92%] sm:max-w-[78%] rounded-2xl border px-3.5 py-2.5 ${meta.bubble}`}>
                                                <div className="flex items-baseline justify-between gap-3 mb-1">
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                                        {meta.name}
                                                    </span>
                                                    <span className="text-[10px] tabular-nums text-slate-400">{turn.at}</span>
                                                </div>
                                                <p className="text-sm leading-relaxed">{highlightText(turn.text, inTranscript)}</p>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </MainLayout>
    );
}
