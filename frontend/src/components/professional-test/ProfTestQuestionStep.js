/**
 * Single-question step with Avito-like mouse integrity zone.
 * Next/Finish controls stay inside the zone so moving to click them
 * does not trigger a false mouse_leave violation.
 */
export default function ProfTestQuestionStep({
    question,
    index,
    total,
    selectedOptionIndex,
    textValue,
    locked,
    warning,
    zoneRef,
    onZoneMouseLeave,
    onSelectOption,
    onTextChange,
    onNext,
    isLast,
}) {
    const options = Array.isArray(question?.options) ? question.options : [];
    const hasOptions = options.length > 0;
    const canProceed =
        locked || (hasOptions ? selectedOptionIndex != null : String(textValue || "").trim());

    return (
        <div className="min-h-[calc(100vh-3.5rem)] flex flex-col px-2 py-2 md:px-3 md:py-3">
            <div
                ref={zoneRef}
                onMouseLeave={onZoneMouseLeave}
                data-testid="prof-integrity-zone"
                className={`relative flex-1 w-full max-w-[1600px] mx-auto min-h-[min(94vh,1100px)] flex flex-col rounded-3xl transition-colors ${
                    locked
                        ? "bg-rose-50/70 border-[3px] border-dashed border-rose-400 shadow-[0_0_0_8px_rgba(251,113,133,0.15)]"
                        : "bg-white border-[3px] border-dashed border-[#4f46e5] shadow-[0_0_0_10px_rgba(79,70,229,0.12)]"
                }`}
            >
                {/* Corner markers — make the safe zone unmistakable */}
                <span
                    className={`pointer-events-none absolute top-3 left-3 w-8 h-8 border-t-4 border-l-4 rounded-tl-lg ${
                        locked ? "border-rose-500" : "border-[#4f46e5]"
                    }`}
                    aria-hidden
                />
                <span
                    className={`pointer-events-none absolute top-3 right-3 w-8 h-8 border-t-4 border-r-4 rounded-tr-lg ${
                        locked ? "border-rose-500" : "border-[#4f46e5]"
                    }`}
                    aria-hidden
                />
                <span
                    className={`pointer-events-none absolute bottom-3 left-3 w-8 h-8 border-b-4 border-l-4 rounded-bl-lg ${
                        locked ? "border-rose-500" : "border-[#4f46e5]"
                    }`}
                    aria-hidden
                />
                <span
                    className={`pointer-events-none absolute bottom-3 right-3 w-8 h-8 border-b-4 border-r-4 rounded-br-lg ${
                        locked ? "border-rose-500" : "border-[#4f46e5]"
                    }`}
                    aria-hidden
                />

                <div
                    className={`mx-4 mt-4 md:mx-8 md:mt-6 rounded-2xl px-4 py-3 md:px-6 md:py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
                        locked
                            ? "bg-rose-100 border border-rose-200"
                            : "bg-[#4f46e5]/15 border border-[#4f46e5]/40"
                    }`}
                >
                    <div>
                        <p
                            className={`text-sm md:text-base font-bold ${
                                locked ? "text-rose-800" : "text-slate-900"
                            }`}
                        >
                            {locked
                                ? "Зона ответа заблокирована — вопрос засчитан как неверный"
                                : "Зона ответа — держите курсор внутри этой рамки"}
                        </p>
                        <p
                            className={`text-xs md:text-sm mt-0.5 ${
                                locked ? "text-rose-700/80" : "text-slate-600"
                            }`}
                        >
                            Выход мыши за пунктирную границу или уход со вкладки делает текущий
                            вопрос неверным.
                        </p>
                    </div>
                    <div className="shrink-0 text-sm text-slate-600 font-medium tabular-nums">
                        Вопрос {index + 1} / {total}
                    </div>
                </div>

                <div className="px-6 md:px-10 mt-4">
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-[#4f46e5] transition-all duration-300"
                            style={{ width: `${((index + 1) / Math.max(total, 1)) * 100}%` }}
                        />
                    </div>
                </div>

                <div className="flex-1 flex flex-col justify-center px-5 py-8 md:px-16 md:py-12 lg:px-24 xl:px-32">
                    <h2
                        className="text-2xl md:text-3xl lg:text-4xl font-bold text-slate-900 leading-snug text-center mb-10 max-w-4xl mx-auto"
                        data-testid={`prof-question-${question.id}`}
                    >
                        {question.text}
                    </h2>

                    <div className="w-full max-w-4xl mx-auto">
                        {hasOptions ? (
                            <div className="space-y-3 md:space-y-4" role="radiogroup" aria-label="Варианты ответа">
                                {options.map((opt, oi) => {
                                    const selected = selectedOptionIndex === oi;
                                    return (
                                        <button
                                            key={`${question.id}-${oi}`}
                                            type="button"
                                            disabled={locked}
                                            onClick={() => onSelectOption(oi, opt)}
                                            data-testid={`prof-option-${oi}`}
                                            className={`w-full text-left px-5 py-4 md:px-6 md:py-5 rounded-2xl border text-base md:text-lg transition-all ${
                                                selected
                                                    ? "border-[#4f46e5] bg-[#4f46e5]/10 ring-2 ring-[#4f46e5]/30"
                                                    : "border-slate-200 hover:border-slate-300 bg-slate-50/80"
                                            } disabled:opacity-70 disabled:cursor-not-allowed`}
                                        >
                                            <span className="font-medium text-slate-900">{opt}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        ) : (
                            <textarea
                                className="w-full border border-slate-200 rounded-2xl px-4 py-3 text-base md:text-lg min-h-[220px] focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/40 disabled:bg-slate-50"
                                value={textValue || ""}
                                disabled={locked}
                                onChange={(e) => onTextChange(e.target.value)}
                                placeholder="Ваш ответ"
                                data-testid="prof-free-text"
                            />
                        )}

                        {warning && (
                            <p
                                className="mt-6 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3"
                                role="alert"
                                data-testid="prof-integrity-warning"
                            >
                                {warning}
                            </p>
                        )}
                    </div>
                </div>

                <div className="flex justify-center px-6 pb-10 pt-2 md:pb-12">
                    <button
                        type="button"
                        disabled={!canProceed}
                        onClick={onNext}
                        data-testid="prof-next"
                        className="px-10 py-3.5 rounded-2xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 disabled:opacity-40 shadow-md"
                    >
                        {isLast ? "Завершить тест" : "Следующий вопрос"}
                    </button>
                </div>
            </div>

            <p className="text-center text-[11px] text-slate-400 mt-2 mb-1">
                Серая область вокруг рамки — вне зоны ответа
            </p>
        </div>
    );
}

