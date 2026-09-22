import React, { useState, useEffect } from 'react';
import {
    createTest,
    updateTest,
    replaceTestQuestions,
    addTestsToVacancy,
} from "../../services/testApi";
import {getVacancies} from "../../services/vacancyApi";
import {generateTest} from "../../services/aiApi";
import {TEST_TYPES, RESULT_TYPES} from "../../config/api";
import {useAlertContext} from "../../context/AlertContext";

/** Map API (`text`) and form (`question_text`) into form state. */
const normalizeQuestions = (list) =>
    (Array.isArray(list) ? list : []).map((q) => ({
        id: q?.id,
        question_text: String(q?.question_text || q?.text || ""),
        options: Array.isArray(q?.options) ? q.options.map((o) => String(o ?? "")) : [],
        correct_option_index:
            q?.correct_option_index != null && Number.isFinite(Number(q.correct_option_index))
                ? Number(q.correct_option_index)
                : null,
    }));

const questionsPayload = (list) =>
    (Array.isArray(list) ? list : [])
        .map((q) => {
            const text = String(q?.text || q?.question_text || "").trim();
            const options = (Array.isArray(q?.options) ? q.options : [])
                .map((o) => String(o || "").trim())
                .filter(Boolean);
            let correct = q?.correct_option_index;
            if (correct != null) {
                correct = Number(correct);
                if (!Number.isFinite(correct) || correct < 0 || correct >= options.length) {
                    correct = null;
                }
            } else {
                correct = null;
            }
            return {
                text,
                options: options.length ? options : null,
                correct_option_index: correct,
            };
        })
        .filter((q) => q.text);

const TestForm = ({ initialData , onClose, onTestAdded, isAiTest = false }) => {
    const [formData, setFormData] = useState({
        name: initialData?.name || '',
        test_type: initialData?.test_type || TEST_TYPES[0],
        results_type: initialData?.results_type || "текстовый результат",
        url: initialData?.url || '',
        description: initialData?.description || '',
        instruction_text: initialData?.instruction_text || '',
        duration_minutes:
            initialData?.duration_minutes != null ? String(initialData.duration_minutes) : '',
    });
    const {showAlert} = useAlertContext();
    const [mode, setMode] = useState("manual");
    const [vacancies, setVacancies] = useState([]);
    const [aiFormData, setAIFormData] = useState({
        topic: "",
        vacancy_id: "",
    })
    const [loading, setLoading] = useState(false);
    const [editingTest] = useState(initialData);
    const [questions, setQuestions] = useState(() => normalizeQuestions(initialData?.questions));


    useEffect(() => {
        const loadVacancies = async () => {
            try {
                const data = await getVacancies();
                setVacancies(Array.isArray(data) ? data : [])
            } catch (e) {
                console.error("Ошибка загрузки вакансий: ", e)
            }
        }
        loadVacancies()
    }, [])

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        try {
            const durationRaw = String(formData.duration_minutes || "").trim();
            const durationMinutes = durationRaw
                ? Math.max(1, Math.min(600, Number(durationRaw) || 0))
                : null;
            const saveBody = {
                name: formData.name,
                test_type: formData.test_type,
                results_type: formData.results_type,
                url: formData.url || null,
                description: formData.description || null,
                instruction_text: formData.instruction_text,
                duration_minutes:
                    formData.test_type === "Вопросно-ответная форма" ? durationMinutes || null : null,
            };

            let result
            if(editingTest?.id) {
                result = await updateTest(editingTest.id, saveBody)
                if (formData.test_type === "Вопросно-ответная форма") {
                    showAlert("Сохраняем вопросы...", "info")
                    await replaceTestQuestions(editingTest.id, questionsPayload(questions))
                }
            } else {
                result = await createTest(saveBody)

                const questionsToAdd = window.generatedTestData?.questions?.length
                    ? window.generatedTestData.questions
                    : questions;
                const payload = questionsPayload(questionsToAdd);
                if (payload.length > 0) {
                    showAlert("Добавляем вопросы...", "info")
                    await replaceTestQuestions(result.id, payload)
                }

                if (window.generatedTestData?.vacancy_ids?.length > 0) {
                    showAlert("Привязываем к вакансиям...", "info");
                    for (const vacancyId of window.generatedTestData.vacancy_ids) {
                        await addTestsToVacancy(Number(vacancyId), [result.id]);
                    }
                }

                delete window.generatedTestData
            }

            showAlert("Тест сохранен", "success")
            onTestAdded?.(result)
            onClose()
        } catch (e) {
            console.error("Ошибка сохранения", e)
            showAlert(`Ошибка: ${e.message}`, "error")
        }
    };

    const handleAddQuestion = () => {
        setQuestions(prev => [...prev, { question_text: "", options: [] }]);
    };

    const handleRemoveQuestion = (index) => {
        setQuestions(prev => prev.filter((_, i) => i !== index));
    };

    const handleQuestionChange = (index, field, value) => {
        setQuestions(prev => prev.map((q, i) => i === index ? { ...q, [field]: value } : q));
    };

    const handleAddOption = (questionIndex) => {
        setQuestions(prev => prev.map((q, i) =>
            i === questionIndex ? { ...q, options: [...(q.options || []), ""] } : q
        ));
    };

    const handleRemoveOption = (questionIndex, optionIndex) => {
        setQuestions(prev => prev.map((q, i) => {
            if (i !== questionIndex) return q;
            const options = q.options.filter((_, oi) => oi !== optionIndex);
            let correct = q.correct_option_index;
            if (correct === optionIndex) correct = null;
            else if (correct != null && correct > optionIndex) correct = correct - 1;
            return { ...q, options, correct_option_index: correct };
        }));
    };

    const handleOptionChange = (questionIndex, optionIndex, value) => {
        setQuestions(prev => prev.map((q, i) =>
            i === questionIndex ? {
                ...q,
                options: q.options.map((opt, oi) => oi === optionIndex ? value : opt)
            } : q
        ));
    };

    const handleAiGenerate = async (e) => {
        e.preventDefault()

        if(!aiFormData.topic || !aiFormData.vacancy_id) {
            showAlert("Заполните все поля", "error")
            return
        }

        try {
            setLoading(true)
            showAlert("Получаем данные вакансии...", "info")

            const allVacancies = await getVacancies();
            if (!Array.isArray(allVacancies)) {
                throw new Error("Не удалось загрузить вакансии");
            }
            const selected = allVacancies.find(v => String(v.id) === String(aiFormData.vacancy_id));

            if (!selected) throw new Error("Вакансия не найдена");

            const descriptionText = `
                Название вакансии: ${selected.name || ''}
                Описание: ${selected.description || 'не указано'}
                `.trim();

            showAlert("Генерируем тест с помощью AI...", "info")

            const generatedTest = await generateTest(aiFormData.topic, descriptionText)

            showAlert("Тест сгенерирован! Добавьте URL и нажмите Сохранить", "info")

            setFormData({
                name: generatedTest.name,
                test_type: "Вопросно-ответная форма",
                results_type: "текстовый результат",
                url: "",
                description: generatedTest.description || "",
                instruction_text: generatedTest.instruction || "",
                duration_minutes: formData.duration_minutes || "",
            })

            const normalized = normalizeQuestions(generatedTest.questions);
            setQuestions(normalized);

            window.generatedTestData = {
                questions: generatedTest.questions,
                vacancy_ids: [aiFormData.vacancy_id],
            }

            setMode("manual")

        } catch (e) {
            console.error("Ошибка AI генерации", e)
            showAlert(`Ошибка: ${e.message}`, "error")
        } finally {
            setLoading(false)
        }
    }

    return (
        <form onSubmit={handleSubmit} className="flex flex-col h-full bg-white rounded-2xl overflow-hidden p-6">
            <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-100">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900">
                        {editingTest ? "Редактировать тест" : "Создать тест"}
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">Настройки и содержание теста</p>
                </div>
                <button type="button" onClick={onClose} className="w-10 h-10 flex items-center justify-center rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-700 transition-colors">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-6">
                {!editingTest && isAiTest && (
                    <div className="bg-gradient-to-br from-indigo-50 to-blue-50 p-6 rounded-2xl border border-indigo-100">
                        <div className="flex items-center gap-2 mb-4">
                            <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                            <h3 className="font-bold text-indigo-900">AI-генерация</h3>
                        </div>
                        
                        <div className="flex bg-white/50 rounded-xl p-1 mb-4 border border-indigo-100/50 w-fit">
                            <button
                                type="button"
                                onClick={() => setMode("manual")}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${mode === "manual" ? "bg-white text-indigo-900 shadow-sm" : "text-indigo-600 hover:bg-white/50"}`}
                            >
                                Вручную
                            </button>
                            <button
                                type="button"
                                onClick={() => setMode("ai")}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${mode === "ai" ? "bg-indigo-600 text-white shadow-sm" : "text-indigo-600 hover:bg-white/50"}`}
                            >
                                Сгенерировать
                            </button>
                        </div>

                        {mode === "ai" && (
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-semibold text-indigo-900 mb-1.5">Тематика теста *</label>
                                    <input
                                        type="text"
                                        value={aiFormData.topic}
                                        onChange={(e) => setAIFormData({ ...aiFormData, topic: e.target.value })}
                                        className="w-full border border-indigo-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                                        placeholder="Например, Оценка soft skills..."
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-semibold text-indigo-900 mb-1.5">Привязать к вакансии *</label>
                                    <div className="relative">
                                        <select
                                            value={aiFormData.vacancy_id}
                                            onChange={(e) => setAIFormData({ ...aiFormData, vacancy_id: e.target.value })}
                                            className="w-full appearance-none border border-indigo-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all cursor-pointer"
                                        >
                                            <option value="">Выберите вакансию</option>
                                            {vacancies.map((vacancy) => (
                                                <option key={vacancy.id} value={vacancy.id}>
                                                    {vacancy.name}
                                                </option>
                                            ))}
                                        </select>
                                        <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-indigo-400">
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                        </div>
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={handleAiGenerate}
                                    disabled={loading}
                                    className="w-full mt-2 bg-indigo-600 text-white px-4 py-2.5 rounded-xl hover:bg-indigo-700 transition-colors shadow-sm text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                                >
                                    {loading ? (
                                        <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Генерация...</>
                                    ) : "Сгенерировать вопросы"}
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {(mode === "manual" || editingTest) && (
                    <div className="space-y-6">
                        <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Настройки теста</h3>
                            
                            <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Название теста *</label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) => handleChange('name', e.target.value)}
                                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all"
                                    required
                                />
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-1.5">Тип теста *</label>
                                    <div className="relative">
                                        <select
                                            value={formData.test_type}
                                            onChange={(e) => handleChange('test_type', e.target.value)}
                                            className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all cursor-pointer disabled:opacity-50"
                                            required 
                                            disabled={isAiTest}
                                        >
                                            {TEST_TYPES.map(type => (
                                                <option key={type} value={type}>{type}</option>
                                            ))}
                                        </select>
                                        <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                        </div>
                                    </div>
                                </div>
                                
                                <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-1.5">Тип результата *</label>
                                    <div className="relative">
                                        <select
                                            value={formData.results_type}
                                            onChange={(e) => handleChange('results_type', e.target.value)}
                                            className="w-full appearance-none border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all cursor-pointer disabled:opacity-50"
                                            required 
                                            disabled={isAiTest}
                                        >
                                            {RESULT_TYPES.map(type => (
                                                <option key={type} value={type}>{type}</option>
                                            ))}
                                        </select>
                                        <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {!isAiTest && (formData.test_type === "url" || formData.test_type === "Вопросно-ответная форма") && (
                                <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-1.5">URL теста</label>
                                    <input
                                        type="url"
                                        value={formData.url}
                                        onChange={(e) => handleChange('url', e.target.value)}
                                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all"
                                        placeholder="https://example.com/test"
                                    />
                                </div>
                            )}

                            {formData.test_type === "Вопросно-ответная форма" && (
                                <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                                        Длительность теста (минуты)
                                    </label>
                                    <input
                                        type="number"
                                        min={1}
                                        max={600}
                                        value={formData.duration_minutes}
                                        onChange={(e) => handleChange("duration_minutes", e.target.value)}
                                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all"
                                        placeholder="Например, 30"
                                        data-testid="test-duration-minutes"
                                    />
                                    <p className="mt-1 text-xs text-slate-500">
                                        По истечении времени публичное прохождение завершится автоматически.
                                    </p>
                                </div>
                            )}
                        </div>

                        <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100 space-y-4">
                            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Описание</h3>

                            <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Описание</label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) => handleChange('description', e.target.value)}
                                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[80px] disabled:opacity-50"
                                    placeholder="Краткое описание теста"
                                    disabled={isAiTest}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Текст инструкции (видит кандидат) *</label>
                                <textarea
                                    value={formData.instruction_text}
                                    onChange={(e) => handleChange('instruction_text', e.target.value)}
                                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px] disabled:opacity-50"
                                    placeholder="Подробная инструкция по прохождению теста"
                                    required 
                                    disabled={isAiTest}
                                />
                            </div>
                        </div>

                        {formData.test_type === "Вопросно-ответная форма" && !isAiTest && (
                            <div className="bg-slate-50/50 p-6 rounded-2xl border border-slate-100">
                                <div className="flex justify-between items-center mb-4">
                                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Вопросы теста</h3>
                                    <button
                                        type="button"
                                        onClick={handleAddQuestion}
                                        className="text-[#cda834] hover:text-[#b8952b] text-sm font-semibold transition-colors"
                                    >
                                        + Добавить вопрос
                                    </button>
                                </div>
                                
                                {questions.length === 0 ? (
                                    <div className="text-center py-6 text-slate-500 border-2 border-dashed border-slate-200 rounded-xl">
                                        Нет вопросов. Нажмите «Добавить вопрос».
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {questions.map((question, qIndex) => (
                                            <div key={question.id ?? `new-${qIndex}`} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm relative group">
                                                <div className="flex justify-between items-start mb-2">
                                                    <label className="block text-sm font-semibold text-slate-700">Вопрос #{qIndex + 1}</label>
                                                    <button type="button" onClick={() => handleRemoveQuestion(qIndex)} className="text-red-500 text-sm hover:text-red-700">Удалить</button>
                                                </div>

                                                <textarea
                                                    value={question.question_text}
                                                    onChange={e => handleQuestionChange(qIndex, "question_text", e.target.value)}
                                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all mb-4"
                                                    rows="2"
                                                    placeholder="Текст вопроса"
                                                    required
                                                />

                                                <div className="pl-4 border-l-2 border-slate-100">
                                                    <div className="flex justify-between items-center mb-2">
                                                        <span className="text-xs font-semibold text-slate-500 uppercase">Варианты ответа</span>
                                                        <button
                                                            type="button"
                                                            onClick={() => handleAddOption(qIndex)}
                                                            className="text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
                                                        >
                                                            + Добавить вариант
                                                        </button>
                                                    </div>

                                                    <div className="space-y-2">
                                                        {(question.options || []).map((opt, oIndex) => (
                                                            <div key={oIndex} className="flex gap-2 items-center">
                                                                <label
                                                                    className="shrink-0 flex items-center gap-1 text-xs text-slate-500 cursor-pointer"
                                                                    title="Правильный ответ"
                                                                >
                                                                    <input
                                                                        type="radio"
                                                                        name={`correct-${qIndex}`}
                                                                        checked={question.correct_option_index === oIndex}
                                                                        onChange={() =>
                                                                            handleQuestionChange(
                                                                                qIndex,
                                                                                "correct_option_index",
                                                                                oIndex
                                                                            )
                                                                        }
                                                                    />
                                                                    верный
                                                                </label>
                                                                <input
                                                                    type="text"
                                                                    value={opt}
                                                                    onChange={e => handleOptionChange(qIndex, oIndex, e.target.value)}
                                                                    className="flex-1 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-slate-400 transition-colors"
                                                                    placeholder={`Вариант ${oIndex + 1}`}
                                                                />
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleRemoveOption(qIndex, oIndex)}
                                                                    className="text-red-400 hover:text-red-600 px-2"
                                                                >
                                                                    ×
                                                                </button>
                                                            </div>
                                                        ))}
                                                    </div>
                                                    <p className="mt-2 text-[11px] text-slate-400">
                                                        Отметьте правильный вариант — без него ответ не будет
                                                        автопроверяться.
                                                    </p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-slate-100">
                <button type="button" onClick={onClose} className="px-5 py-2.5 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors">
                    Отмена
                </button>
                <button 
                    type="submit" 
                    disabled={mode === "ai" && !editingTest}
                    className="px-6 py-2.5 text-sm font-medium text-white bg-slate-900 rounded-xl hover:bg-slate-800 shadow-sm transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    Сохранить
                </button>
            </div>
        </form>
    );
}

export default TestForm;
