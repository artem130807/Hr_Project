import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
    getPublicPsychInstrument,
    submitPublicPsychResult,
} from "../services/psychTestApi";
import {
    blockNumber,
    clearTakeSession,
    createTakeSession,
} from "../psychometrics/psychPresentation";
import { localISODate } from "../psychometrics/psychDates";
import {
    psychTakeDraftScopeFromSearch,
    writePsychTakeDraft,
} from "../psychometrics/psychTakeDraft";

const LETTERS = ["A", "B", "C", "D"];
const INACTIVITY_SEC = 60;

function isAnswered(item, value) {
    if (!item) return false;
    if (item.module === "disc") {
        return Boolean(value?.most && value?.least && value.most !== value.least);
    }
    if (item.module === "avp") return value >= 1 && value <= 5;
    return ["A", "B", "C", "D"].includes(value);
}

export default function PsychTakePage() {
    const { instrumentId } = useParams();
    const draftScope = useMemo(
        () => psychTakeDraftScopeFromSearch(typeof window !== "undefined" ? window.location.search : ""),
        []
    );
    const [instrument, setInstrument] = useState(null);
    const [sessionItems, setSessionItems] = useState([]);
    const [presentation, setPresentation] = useState(null);
    const [sessionSeed, setSessionSeed] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [fullName, setFullName] = useState("");
    const [position, setPosition] = useState("");
    const [birthDate, setBirthDate] = useState("");
    const [takenAt] = useState(() => localISODate());
    const [answers, setAnswers] = useState({});
    const [questionIndex, setQuestionIndex] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [done, setDone] = useState(null);
    const [discColumn, setDiscColumn] = useState("most");
    const [notice, setNotice] = useState("");
    const [progressReady, setProgressReady] = useState(false);

    const startedAtRef = useRef(null);
    const shownAtRef = useRef(Date.now());
    const lastActivityRef = useRef(Date.now());
    const activeMsRef = useRef(0);
    const lastTickRef = useRef(Date.now());
    const latenciesRef = useRef({});
    const visibleRef = useRef(true);
    const submittedRef = useRef(false);

    useEffect(() => {
        let cancelled = false;
        setProgressReady(false);
        submittedRef.current = false;
        (async () => {
            try {
                setLoading(true);
                setError(null);
                const data = await getPublicPsychInstrument(instrumentId);
                if (cancelled) return;
                setInstrument(data);
                const session = createTakeSession(data, undefined, { scope: draftScope });
                setSessionItems(session.items);
                setPresentation(session.presentation);
                setSessionSeed(session.seed);
                const draft = session.draft;
                if (draft) {
                    setAnswers(draft.answers || {});
                    setQuestionIndex(draft.questionIndex || 0);
                    setFullName(draft.fullName || "");
                    setPosition(draft.position || "");
                    setBirthDate(draft.birthDate || "");
                    startedAtRef.current = draft.startedAt || Date.now();
                    activeMsRef.current = draft.activeMs || 0;
                    latenciesRef.current = { ...(draft.latencies || {}) };
                } else {
                    setAnswers({});
                    setQuestionIndex(0);
                    startedAtRef.current = Date.now();
                    activeMsRef.current = 0;
                    latenciesRef.current = {};
                }
                setProgressReady(true);
            } catch (e) {
                if (!cancelled) setError(e.message || String(e));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [instrumentId, draftScope]);

    const items = sessionItems;
    const currentItem = items[questionIndex] || null;
    const currentCode = currentItem?.code;
    const currentValue = currentCode ? answers[currentCode] : null;
    const currentAnswered = isAnswered(currentItem, currentValue);
    const isLastQuestion = questionIndex >= items.length - 1;
    const answeredCount = items.filter((it) => isAnswered(it, answers[it.code])).length;
    const scaleLabels = useMemo(() => instrument?.answer_scale?.labels || {}, [instrument]);

    const draftSnapshotRef = useRef(null);
    draftSnapshotRef.current = {
        instrumentId,
        scope: draftScope,
        seed: sessionSeed,
        codes: items.map((it) => it.code),
        answers,
        questionIndex,
        fullName,
        position,
        birthDate,
        startedAt: startedAtRef.current,
        activeMs: activeMsRef.current,
        latencies: latenciesRef.current,
    };

    useEffect(() => {
        if (!progressReady || done || submitting) return undefined;
        const persist = () => {
            const snap = draftSnapshotRef.current;
            if (submittedRef.current || done || !snap?.instrumentId || !snap.codes?.length) return;
            writePsychTakeDraft(snap.instrumentId, snap, { scope: snap.scope });
        };
        const timer = window.setTimeout(persist, 200);
        return () => window.clearTimeout(timer);
    }, [answers, questionIndex, fullName, position, birthDate, progressReady, done, submitting, sessionSeed, items]);

    useEffect(() => {
        if (!progressReady) return undefined;
        const persist = () => {
            const snap = draftSnapshotRef.current;
            if (submittedRef.current || !snap?.instrumentId || !snap.codes?.length) return;
            writePsychTakeDraft(snap.instrumentId, snap, { scope: snap.scope });
        };
        window.addEventListener("pagehide", persist);
        window.addEventListener("beforeunload", persist);
        return () => {
            persist();
            window.removeEventListener("pagehide", persist);
            window.removeEventListener("beforeunload", persist);
        };
    }, [progressReady, done]);

    useEffect(() => {
        shownAtRef.current = Date.now();
        lastActivityRef.current = Date.now();
        setDiscColumn("most");
        setNotice("");
    }, [questionIndex, currentCode]);

    useEffect(() => {
        const onVis = () => {
            visibleRef.current = document.visibilityState === "visible";
            lastTickRef.current = Date.now();
        };
        const tick = () => {
            const now = Date.now();
            if (
                visibleRef.current
                && now - lastActivityRef.current <= INACTIVITY_SEC * 1000
            ) {
                activeMsRef.current += now - lastTickRef.current;
            }
            lastTickRef.current = now;
        };
        const id = setInterval(tick, 1000);
        document.addEventListener("visibilitychange", onVis);
        return () => {
            clearInterval(id);
            document.removeEventListener("visibilitychange", onVis);
        };
    }, []);

    const markLatency = (code) => {
        if (!code || latenciesRef.current[code] != null) return;
        latenciesRef.current[code] = Math.max(0, Date.now() - shownAtRef.current);
        lastActivityRef.current = Date.now();
    };

    const setDiscChoice = (letter, column) => {
        if (!currentItem) return;
        const prev = answers[currentItem.code] || {};
        const other = column === "most" ? "least" : "most";
        if (prev[other] === letter) {
            setNotice("Один вариант нельзя выбрать сразу в обеих колонках.");
            lastActivityRef.current = Date.now();
            return;
        }
        setNotice("");
        setError(null);
        setAnswers((p) => ({
            ...p,
            [currentItem.code]: { ...prev, [column]: letter },
        }));
        lastActivityRef.current = Date.now();
    };

    const goNext = () => {
        if (!currentAnswered) {
            setError(
                currentItem?.module === "disc"
                    ? "Отметьте один вариант «более похоже» и один «менее похоже»."
                    : currentItem?.module === "sjt"
                      ? "Сначала выберите один вариант."
                      : "Сначала выберите оценку 1–5 для текущего вопроса."
            );
            return;
        }
        markLatency(currentCode);
        setError(null);
        setQuestionIndex((prev) => Math.min(prev + 1, items.length - 1));
    };

    useEffect(() => {
        if (!currentItem || submitting || done) return;
        const onKeyDown = (event) => {
            const target = event.target;
            if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
                return;
            }
            lastActivityRef.current = Date.now();
            if (event.key === "Tab" && currentItem.module === "disc") {
                event.preventDefault();
                setDiscColumn((c) => (c === "most" ? "least" : "most"));
                return;
            }
            if (currentItem.module === "avp" && /^[1-5]$/.test(event.key)) {
                event.preventDefault();
                const value = Number(event.key);
                setAnswers((p) => ({ ...p, [currentItem.code]: value }));
                setError(null);
                markLatency(currentItem.code);
                if (!isLastQuestion) {
                    setTimeout(() => setQuestionIndex((prev) => Math.min(prev + 1, items.length - 1)), 180);
                }
                return;
            }
            if ((currentItem.module === "disc" || currentItem.module === "sjt") && /^[1-4]$/.test(event.key)) {
                event.preventDefault();
                const letter = LETTERS[Number(event.key) - 1];
                if (currentItem.module === "disc") {
                    setDiscChoice(letter, discColumn);
                } else {
                    setAnswers((p) => ({ ...p, [currentItem.code]: letter }));
                    setError(null);
                }
                return;
            }
            if (currentItem.module === "sjt" && /^[a-dA-D]$/.test(event.key)) {
                event.preventDefault();
                setAnswers((p) => ({ ...p, [currentItem.code]: event.key.toUpperCase() }));
                setError(null);
                return;
            }
            if (event.key === "Enter" || event.key === "ArrowRight") {
                event.preventDefault();
                goNext();
            }
            if (event.key === "ArrowLeft") {
                event.preventDefault();
                setQuestionIndex((prev) => Math.max(0, prev - 1));
            }
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    });

    const handleSubmit = async () => {
        if (!fullName.trim() || !position.trim() || !birthDate || !takenAt) {
            setError("Заполните ФИО, должность, дату рождения и дату прохождения.");
            return;
        }
        if (answeredCount < items.length) {
            setError(`Нужно ответить на все вопросы: ${answeredCount} из ${items.length}.`);
            return;
        }
        markLatency(currentCode);
        try {
            setSubmitting(true);
            setError(null);
            const wall = startedAtRef.current
                ? Math.max(0, Math.round((Date.now() - startedAtRef.current) / 1000))
                : null;
            const result = await submitPublicPsychResult({
                instrument_id: instrumentId,
                full_name: fullName.trim(),
                position: position.trim(),
                taken_at: takenAt,
                birth_date: birthDate,
                answers,
                timing: {
                    active_duration_sec: Math.round(activeMsRef.current / 1000),
                    wall_duration_sec: wall,
                    latencies_ms: latenciesRef.current,
                    presentation: {
                        seed: sessionSeed,
                        block_order: presentation?.block_order,
                        item_order: items.map((it) => it.code),
                    },
                },
            });
            submittedRef.current = true;
            clearTakeSession(instrumentId, undefined, { scope: draftScope });
            setDone(result);
        } catch (e) {
            setError(e.message || String(e));
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-500">
                Загрузка опросника…
            </div>
        );
    }

    if (error && !instrument) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
                <div className="bg-white rounded-2xl border border-slate-200 p-8 max-w-lg text-center">
                    <h1 className="text-xl font-bold text-slate-900 mb-2">Не удалось открыть тест</h1>
                    <p className="text-slate-600 text-sm">{error}</p>
                </div>
            </div>
        );
    }

    if (done) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6" data-testid="psych-take-done">
                <div className="bg-white rounded-2xl border border-slate-200 p-8 max-w-lg text-center shadow-sm">
                    <h1 className="text-2xl font-bold text-slate-900 mb-2">Спасибо!</h1>
                    <p className="text-slate-600 text-sm">Ответы сохранены.</p>
                </div>
            </div>
        );
    }

    const selectedCls = "bg-orange-500 text-white border-orange-500";
    const idleCls = "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100";

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-100 to-slate-50" data-testid="psych-take-page">
            <div className="max-w-3xl mx-auto px-4 py-8">
                <header className="mb-8">
                    <h1 className="text-3xl font-bold text-slate-900 leading-tight">{instrument.name}</h1>
                    {instrument.instruction && (
                        <p className="mt-3 text-sm text-slate-700 bg-white/80 border border-slate-200 rounded-xl p-4">
                            {instrument.instruction}
                        </p>
                    )}
                </header>

                <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 mb-6 space-y-4">
                    <h2 className="text-sm font-semibold text-slate-800">Данные участника</h2>
                    <div className="grid md:grid-cols-2 gap-3">
                        <label className="block text-sm">
                            <span className="text-slate-500">ФИО</span>
                            <input
                                className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                placeholder="Иванов Иван Иванович"
                                data-testid="psych-full-name"
                            />
                        </label>
                        <label className="block text-sm">
                            <span className="text-slate-500">Должность / вакансия</span>
                            <input
                                className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2"
                                value={position}
                                onChange={(e) => setPosition(e.target.value)}
                                data-testid="psych-position"
                            />
                        </label>
                        <label className="block text-sm">
                            <span className="text-slate-500">Дата рождения</span>
                            <input
                                type="date"
                                className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2"
                                value={birthDate}
                                max={takenAt || localISODate()}
                                onChange={(e) => setBirthDate(e.target.value)}
                                data-testid="psych-birth-date"
                            />
                        </label>
                        <label className="block text-sm">
                            <span className="text-slate-500">Дата прохождения</span>
                            <input
                                type="date"
                                className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 bg-slate-50"
                                value={takenAt}
                                readOnly
                                data-testid="psych-taken-at"
                            />
                            <span className="mt-1 block text-xs text-slate-400">Сегодня, подставляется автоматически</span>
                        </label>
                    </div>
                </section>

                <div className="flex justify-between items-center mb-3 text-sm text-slate-500">
                    <span>Задание {Math.min(questionIndex + 1, items.length)} из {items.length}</span>
                    <span>Блок {blockNumber(currentItem?.module, presentation)} из {presentation?.block_count || 3}</span>
                </div>
                <div className="h-1.5 bg-slate-200 rounded-full mb-6 overflow-hidden">
                    <div
                        className="h-full bg-orange-500"
                        style={{ width: `${items.length ? ((questionIndex + 1) / items.length) * 100 : 0}%` }}
                    />
                </div>

                <div className="mb-6">
                    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm" data-testid={`psych-item-${currentItem?.num || "none"}`}>
                        {currentItem?.module === "disc" && (
                            <>
                                <p className="text-sm font-semibold text-slate-900 mb-4">{currentItem.prompt}</p>
                                <div className="grid md:grid-cols-2 gap-4">
                                    {[
                                        ["most", "Более похоже на меня"],
                                        ["least", "Менее похоже на меня"],
                                    ].map(([col, label]) => (
                                        <div
                                            key={col}
                                            className={`rounded-xl border p-3 ${discColumn === col ? "border-orange-300 bg-orange-50/40" : "border-slate-200"}`}
                                        >
                                            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                                                {label}
                                            </div>
                                            <div className="grid gap-2">
                                                {LETTERS.map((letter, idx) => (
                                                    <button
                                                        key={letter}
                                                        type="button"
                                                        onClick={() => {
                                                            setDiscColumn(col);
                                                            setDiscChoice(letter, col);
                                                        }}
                                                        className={`min-h-[44px] px-3 py-2 rounded-xl text-sm font-medium border text-left ${
                                                            currentValue?.[col] === letter ? selectedCls : idleCls
                                                        }`}
                                                    >
                                                        {idx + 1}. {currentItem.options?.[letter]}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                <p className="mt-3 text-xs text-slate-400">
                                    Клавиши 1–4 выбирают вариант в активной колонке, Tab переключает колонку, Enter — далее.
                                </p>
                            </>
                        )}

                        {currentItem?.module === "avp" && (
                            <>
                                <p className="text-sm text-slate-800 mb-4">{currentItem.text}</p>
                                <div className="grid gap-2 sm:grid-cols-5">
                                    {[1, 2, 3, 4, 5].map((v) => (
                                        <button
                                            key={v}
                                            type="button"
                                            onClick={() => {
                                                setAnswers((p) => ({ ...p, [currentItem.code]: v }));
                                                setError(null);
                                                markLatency(currentItem.code);
                                                if (!isLastQuestion) {
                                                    setTimeout(
                                                        () => setQuestionIndex((prev) => Math.min(prev + 1, items.length - 1)),
                                                        180
                                                    );
                                                }
                                            }}
                                            className={`min-h-[44px] px-3 py-2 rounded-xl text-sm font-medium border ${
                                                currentValue === v ? selectedCls : idleCls
                                            }`}
                                        >
                                            {v}
                                        </button>
                                    ))}
                                </div>
                                <p className="mt-3 text-xs text-slate-500">
                                    1 — {scaleLabels[1] || scaleLabels["1"] || "совсем не похоже"}; 5 — {scaleLabels[5] || scaleLabels["5"] || "очень похоже"}.
                                    Клавиши 1–5 отвечают и переходят дальше.
                                </p>
                            </>
                        )}

                        {currentItem?.module === "sjt" && (
                            <>
                                {currentItem.title && (
                                    <div className="text-xs font-semibold text-slate-400 mb-1">{currentItem.title}</div>
                                )}
                                <p className="text-sm text-slate-800 mb-4">{currentItem.prompt}</p>
                                <div className="grid gap-2">
                                    {LETTERS.map((letter, idx) => (
                                        <button
                                            key={letter}
                                            type="button"
                                            onClick={() => {
                                                setAnswers((p) => ({ ...p, [currentItem.code]: letter }));
                                                setError(null);
                                                lastActivityRef.current = Date.now();
                                            }}
                                            className={`min-h-[44px] px-3 py-2 rounded-xl text-sm font-medium border text-left ${
                                                currentValue === letter ? selectedCls : idleCls
                                            }`}
                                        >
                                            {letter}. {currentItem.options?.[letter]}
                                        </button>
                                    ))}
                                </div>
                                <p className="mt-3 text-xs text-slate-400">Клавиши 1–4 или A–D выбирают ответ, Enter — далее.</p>
                            </>
                        )}
                    </div>
                </div>

                {(error || notice) && (
                    <p className="text-sm text-red-600 mb-4" role="alert">
                        {error || notice}
                    </p>
                )}

                <div className="flex flex-wrap gap-3 justify-between items-center sticky bottom-4 bg-white/90 backdrop-blur border border-slate-200 rounded-2xl p-3 shadow-lg">
                    <div className="flex gap-2">
                        <button
                            type="button"
                            disabled={questionIndex <= 0}
                            onClick={() => {
                                setError(null);
                                setQuestionIndex((p) => Math.max(0, p - 1));
                            }}
                            className="min-h-[44px] px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium disabled:opacity-40"
                        >
                            Назад
                        </button>
                        <button
                            type="button"
                            disabled={isLastQuestion}
                            onClick={goNext}
                            className={`min-h-[44px] px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium disabled:opacity-40 ${
                                isLastQuestion ? "hidden" : ""
                            }`}
                        >
                            Далее
                        </button>
                    </div>
                    {isLastQuestion && answeredCount >= items.length && items.length > 0 ? (
                        <button
                            type="button"
                            disabled={submitting}
                            onClick={handleSubmit}
                            data-testid="psych-submit"
                            className="min-h-[44px] px-5 py-2.5 rounded-xl bg-orange-500 text-white text-sm font-semibold hover:bg-orange-600 shadow-md disabled:opacity-50"
                        >
                            {submitting ? "Отправка…" : "Отправить результаты"}
                        </button>
                    ) : null}
                </div>
            </div>
        </div>
    );
}
