import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
    getPublicProfessionalTest,
    submitPublicProfessionalResult,
} from "../services/publicProfessionalTestApi";
import { useProfTestIntegrity } from "../hooks/useProfTestIntegrity";
import { useProfTestTimer } from "../hooks/useProfTestTimer";
import ProfTestQuestionStep from "../components/professional-test/ProfTestQuestionStep";
import ProfTestTimerBar from "../components/professional-test/ProfTestTimerBar";
import {
    answersForSubmit,
    buildProfAnswerEntry,
    fillUnansweredAsTimedOut,
    markQuestionViolated,
} from "../utils/profTestTake";

const PHASE_INTRO = "intro";
const PHASE_QUESTION = "question";
const PHASE_DONE = "done";

export default function ProfessionalTakePage() {
    const { testId } = useParams();
    const qs = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
    const candidateIdFromLink = qs.get("candidate_id");
    const resultIdFromLink = qs.get("result_id");
    const candidateIdNum = Number(candidateIdFromLink);
    const resultIdNum = Number(resultIdFromLink);
    const linkedToCandidate =
        (Number.isFinite(candidateIdNum) && candidateIdNum > 0)
        || (Number.isFinite(resultIdNum) && resultIdNum > 0);
    const [test, setTest] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [phase, setPhase] = useState(PHASE_INTRO);
    const [fullName, setFullName] = useState("");
    const [position, setPosition] = useState("");
    const [takenAt, setTakenAt] = useState(() => new Date().toISOString().slice(0, 10));
    const [answers, setAnswers] = useState({});
    const [questionIndex, setQuestionIndex] = useState(0);
    const [warning, setWarning] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [done, setDone] = useState(null);
    const [, setTimedOut] = useState(false);
    const startedAtRef = useRef(null);
    const submittingRef = useRef(false);
    const answersRef = useRef(answers);
    const questionIndexRef = useRef(questionIndex);
    const integrityRef = useRef({ tab_blur_count: 0, mouse_leave_count: 0 });

    useEffect(() => {
        answersRef.current = answers;
    }, [answers]);
    useEffect(() => {
        questionIndexRef.current = questionIndex;
    }, [questionIndex]);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                setLoading(true);
                setError(null);
                const data = await getPublicProfessionalTest(testId);
                if (!cancelled) setTest(data);
            } catch (e) {
                if (!cancelled) setError(e.message || String(e));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [testId]);

    const questions = useMemo(() => test?.questions || [], [test]);
    const currentQuestion = questions[questionIndex] || null;
    const inQuestions = phase === PHASE_QUESTION && Boolean(currentQuestion);

    const finalizeSubmit = useCallback(
        async ({ timedOut: isTimedOut = false, answersOverride = null } = {}) => {
            if (submittingRef.current) return;
            submittingRef.current = true;
            setSubmitting(true);
            setError(null);
            try {
                const sourceAnswers = answersOverride || answersRef.current;
                const prepared = isTimedOut
                    ? fillUnansweredAsTimedOut(sourceAnswers, questions)
                    : sourceAnswers;
                const payloadAnswers = answersForSubmit(prepared, questions);
                if (!Object.keys(payloadAnswers).length) {
                    questions.forEach((q) => {
                        payloadAnswers[String(q.id)] = buildProfAnswerEntry({
                            forcedIncorrect: true,
                        });
                    });
                }
                const durationSeconds = startedAtRef.current
                    ? Math.max(0, Math.round((Date.now() - startedAtRef.current) / 1000))
                    : null;
                const result = await submitPublicProfessionalResult({
                    test_id: Number(testId),
                    candidate_id: Number.isFinite(candidateIdNum) && candidateIdNum > 0
                        ? candidateIdNum
                        : undefined,
                    result_id: Number.isFinite(resultIdNum) && resultIdNum > 0
                        ? resultIdNum
                        : undefined,
                    full_name: linkedToCandidate ? undefined : fullName.trim(),
                    position: linkedToCandidate ? undefined : position.trim(),
                    taken_at: linkedToCandidate ? undefined : takenAt,
                    answers: payloadAnswers,
                    timed_out: Boolean(isTimedOut),
                    integrity: {
                        duration_seconds: durationSeconds,
                        timed_out: Boolean(isTimedOut),
                        ...integrityRef.current,
                    },
                });
                setDone(result);
                setPhase(PHASE_DONE);
            } catch (e) {
                setError(e.message || String(e));
                submittingRef.current = false;
            } finally {
                setSubmitting(false);
            }
        },
        [fullName, position, takenAt, questions, testId, linkedToCandidate, candidateIdNum, resultIdNum]
    );

    const lockCurrentQuestion = useCallback((violation, message) => {
        const q = questions[questionIndexRef.current];
        if (!q) return false;
        const key = String(q.id);
        if (answersRef.current[key]?.forced_incorrect) return false;
        if (violation === "tab_blur") {
            integrityRef.current.tab_blur_count += 1;
        }
        if (violation === "mouse_leave") {
            integrityRef.current.mouse_leave_count += 1;
        }
        const next = markQuestionViolated(answersRef.current, q.id, violation);
        answersRef.current = next;
        setAnswers(next);
        setWarning(message);
        return true;
    }, [questions]);

    const { zoneRef, tabBlurCount, mouseLeaveCount, handleZoneMouseLeave, resetCounters } =
        useProfTestIntegrity({
            enabled: inQuestions && !submitting && phase !== PHASE_DONE,
            onTabBlur: () =>
                lockCurrentQuestion(
                    "tab_blur",
                    "Обнаружен уход со вкладки — текущий вопрос засчитан как неверный."
                ),
            onMouseLeave: () =>
                lockCurrentQuestion(
                    "mouse_leave",
                    "Курсор покинул зону ответа — текущий вопрос засчитан как неверный."
                ),
        });

    const totalSeconds =
        test?.duration_minutes != null && Number(test.duration_minutes) > 0
            ? Math.floor(Number(test.duration_minutes) * 60)
            : null;

    const { hasTimer, remainingSeconds, formatted } = useProfTestTimer(test?.duration_minutes, {
        enabled: inQuestions,
        onExpire: () => {
            setTimedOut(true);
            finalizeSubmit({ timedOut: true });
        },
    });

    const handleStart = () => {
        if (!linkedToCandidate && (!fullName.trim() || !position.trim() || !takenAt)) {
            setError("Заполните ФИО, должность и дату.");
            return;
        }
        if (!questions.length) {
            setError("В тесте нет вопросов.");
            return;
        }
        setError(null);
        setWarning("");
        setAnswers({});
        setQuestionIndex(0);
        integrityRef.current = { tab_blur_count: 0, mouse_leave_count: 0 };
        resetCounters();
        startedAtRef.current = Date.now();
        submittingRef.current = false;
        setPhase(PHASE_QUESTION);
    };

    const currentEntry = currentQuestion ? answers[String(currentQuestion.id)] : null;

    const selectOption = (optionIndex, optionText) => {
        if (!currentQuestion || currentEntry?.forced_incorrect) return;
        setAnswers((prev) => ({
            ...prev,
            [String(currentQuestion.id)]: buildProfAnswerEntry({
                value: optionText,
                optionIndex,
                violations: prev[String(currentQuestion.id)]?.violations || [],
            }),
        }));
        setWarning("");
    };

    const changeText = (value) => {
        if (!currentQuestion || currentEntry?.forced_incorrect) return;
        setAnswers((prev) => ({
            ...prev,
            [String(currentQuestion.id)]: buildProfAnswerEntry({
                value,
                optionIndex: null,
                violations: prev[String(currentQuestion.id)]?.violations || [],
            }),
        }));
    };

    const goNext = () => {
        if (questionIndex >= questions.length - 1) {
            finalizeSubmit({ timedOut: false });
            return;
        }
        setWarning("");
        setQuestionIndex((i) => i + 1);
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-500">
                Загрузка теста…
            </div>
        );
    }

    if (error && !test) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
                <div className="bg-white rounded-2xl border border-slate-200 p-8 max-w-lg text-center">
                    <h1 className="text-xl font-bold text-slate-900 mb-2">Не удалось открыть тест</h1>
                    <p className="text-slate-600 text-sm">{error}</p>
                </div>
            </div>
        );
    }

    if (phase === PHASE_DONE || done) {
        return (
            <div
                className="min-h-screen bg-slate-50 flex items-center justify-center p-6"
                data-testid="prof-take-done"
            >
                <div className="bg-white rounded-2xl border border-slate-200 p-8 max-w-lg text-center shadow-sm">
                    <h1 className="text-2xl font-bold text-slate-900 mb-2">Спасибо!</h1>
                    <p className="text-slate-600 text-sm">Ответы сохранены.</p>
                    {done?.max_score != null && done.max_score > 0 && (
                        <p className="mt-4 text-sm font-medium text-slate-800" data-testid="prof-score">
                            Результат: {done.score ?? 0} / {done.max_score}
                        </p>
                    )}
                    {(tabBlurCount > 0 || mouseLeaveCount > 0) && (
                        <p className="mt-2 text-xs text-slate-400">
                            Нарушения: вкладка {tabBlurCount}, курсор {mouseLeaveCount}
                        </p>
                    )}
                </div>
            </div>
        );
    }

    if (phase === PHASE_INTRO) {
        return (
            <div className="min-h-screen bg-gradient-to-b from-slate-100 to-slate-50" data-testid="prof-take-page">
                <div className="max-w-2xl mx-auto px-4 py-12">
                    <header className="mb-8 text-center">
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                            Профессиональный тест
                        </p>
                        <h1 className="text-3xl md:text-4xl font-bold text-slate-900 leading-tight">
                            {test.name}
                        </h1>
                        {test.description && (
                            <p className="mt-4 text-sm text-slate-600">{test.description}</p>
                        )}
                    </header>

                    <section className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 md:p-8 space-y-5">
                        {test.instruction && (
                            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-100 rounded-2xl p-4">
                                {test.instruction}
                            </div>
                        )}

                        <div className="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 space-y-1">
                            <p className="font-semibold">Правила честного прохождения</p>
                            <ul className="list-disc pl-5 space-y-1 text-amber-800/90">
                                <li>Вопросы показываются по одному — нельзя вернуться назад.</li>
                                <li>
                                    Держите курсор внутри выделенной зоны ответа. Выход за пределы
                                    засчитывает вопрос как неверный.
                                </li>
                                <li>Переключение вкладок / уход из окна — вопрос становится неверным.</li>
                                {test.duration_minutes ? (
                                    <li>
                                        На тест отведено {test.duration_minutes} мин. По истечении
                                        времени ответы отправятся автоматически.
                                    </li>
                                ) : null}
                            </ul>
                        </div>

                        {!linkedToCandidate && (
                        <div className="grid gap-3">
                            <label className="block text-sm">
                                <span className="text-slate-500">ФИО</span>
                                <input
                                    className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2.5"
                                    value={fullName}
                                    onChange={(e) => setFullName(e.target.value)}
                                    placeholder="Иванов Иван Иванович"
                                    data-testid="prof-full-name"
                                />
                            </label>
                            <label className="block text-sm">
                                <span className="text-slate-500">Должность / специальность</span>
                                <input
                                    className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2.5"
                                    value={position}
                                    onChange={(e) => setPosition(e.target.value)}
                                    data-testid="prof-position"
                                />
                            </label>
                            <label className="block text-sm">
                                <span className="text-slate-500">Дата</span>
                                <input
                                    type="date"
                                    className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2.5"
                                    value={takenAt}
                                    onChange={(e) => setTakenAt(e.target.value)}
                                    data-testid="prof-taken-at"
                                />
                            </label>
                        </div>
                        )}

                        {error && (
                            <p className="text-sm text-red-600" role="alert">
                                {error}
                            </p>
                        )}

                        <button
                            type="button"
                            onClick={handleStart}
                            data-testid="prof-start"
                            className="w-full py-3.5 rounded-2xl bg-slate-900 text-white font-semibold hover:bg-slate-800 shadow-md"
                        >
                            Начать тест
                        </button>
                    </section>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-100 to-slate-50" data-testid="prof-take-page">
            {hasTimer && (
                <ProfTestTimerBar
                    formatted={formatted}
                    remainingSeconds={remainingSeconds}
                    totalSeconds={totalSeconds}
                />
            )}

            {submitting ? (
                <div className="flex items-center justify-center min-h-[60vh] text-slate-500">
                    Отправка результатов…
                </div>
            ) : (
                <ProfTestQuestionStep
                    question={currentQuestion}
                    index={questionIndex}
                    total={questions.length}
                    selectedOptionIndex={currentEntry?.option_index ?? null}
                    textValue={currentEntry?.value || ""}
                    locked={Boolean(currentEntry?.forced_incorrect)}
                    warning={warning}
                    zoneRef={zoneRef}
                    onZoneMouseLeave={handleZoneMouseLeave}
                    onSelectOption={selectOption}
                    onTextChange={changeText}
                    onNext={goNext}
                    isLast={questionIndex >= questions.length - 1}
                />
            )}

            {error && (
                <p className="text-center text-sm text-red-600 pb-6" role="alert">
                    {error}
                </p>
            )}
        </div>
    );
}
