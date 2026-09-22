import { useState } from "react";
import { professionalPublicTakePath } from "../../config/navConfig";
import { useAlertContext } from "../../context/AlertContext";

export default function TestList({tests, onTestDeleted, onTestClick, onTestEdit, psychCatalog}) {
    const { showAlert } = useAlertContext();
    const [copiedId, setCopiedId] = useState(null);
    const professionalTests = (tests || []).filter(t => t.test_type !== "Психологический тест");
    const legacyPsych = (tests || []).filter(t => t.test_type === "Психологический тест");

    const copyLink = async (testId) => {
        const path = professionalPublicTakePath(testId);
        const url = `${window.location.origin}${path}`;
        try {
            await navigator.clipboard.writeText(url);
            setCopiedId(testId);
            showAlert("Ссылка скопирована", "success");
            setTimeout(() => setCopiedId(null), 2000);
        } catch {
            showAlert(`Скопируйте вручную: ${url}`, "warning");
        }
    };

    if ((!tests || tests.length === 0) && !psychCatalog) {
        return (
            <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
                </div>
                <h3 className="text-lg font-medium text-slate-800">Тестов пока нет</h3>
                <p className="text-slate-500 mt-1">Создайте новый тест или сгенерируйте с помощью ИИ.</p>
            </div>
        );
    }

    const renderTestGroup = (groupTests, title) => (
        <div className="mb-8 last:mb-0">
            {title && (
                <div className="flex items-center gap-3 mb-4">
                    <h2 className="text-xl font-bold text-slate-900">{title}</h2>
                    <span className="px-2.5 py-0.5 bg-slate-100 text-slate-600 rounded-full text-xs font-semibold">
                        {groupTests.length}
                    </span>
                </div>
            )}
            
            {groupTests.length === 0 ? (
                <p className="text-slate-500 text-sm italic py-4">Нет тестов в этой категории.</p>
            ) : (
                <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'>
                    {groupTests.map(test => (
                        <div key={test.id} className="bg-white rounded-2xl shadow-sm border border-slate-200/60 hover:shadow-md transition-shadow flex flex-col overflow-hidden group">
                            <div className="p-6 flex-1">
                                <div className="mb-4">
                                    <div className="flex justify-between items-start gap-4 mb-2">
                                        <h3 className="text-lg font-bold text-slate-900 leading-tight group-hover:text-blue-600 transition-colors">{test.name}</h3>
                                        <div className="flex shrink-0">
                                            {test.test_type === "Вопросно-ответная форма" ? (
                                                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center" title="С вариантами ответов">
                                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg>
                                                </div>
                                            ) : test.test_type === "Психологический тест" ? (
                                                <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-700 flex items-center justify-center" title="Психологический">
                                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                                </div>
                                            ) : (
                                                <div className="w-8 h-8 rounded-lg bg-slate-50 text-slate-500 flex items-center justify-center" title="Внешний тест (URL)">
                                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex flex-wrap gap-2">
                                        <span className="px-2 py-1 bg-slate-50 text-slate-600 border border-slate-200/60 rounded text-[10px] font-bold uppercase tracking-wider">{test.test_type}</span>
                                        <span className="px-2 py-1 bg-slate-50 text-slate-600 border border-slate-200/60 rounded text-[10px] font-bold uppercase tracking-wider">{test.results_type}</span>
                                    </div>
                                </div>

                                {test.description && (
                                    <div className="mb-4">
                                        <p className="text-sm text-slate-500 line-clamp-3">{test.description}</p>
                                    </div>
                                )}

                                {test.url && (
                                    <a href={test.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors mb-4">
                                        Внешняя ссылка
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                                    </a>
                                )}
                            </div>

                            <div className="p-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between gap-2">
                                {test.created_at ? (
                                    <div className="text-xs font-medium text-slate-400">
                                        Создан: {new Date(test.created_at).toLocaleDateString("ru-RU")}
                                    </div>
                                ) : (
                                    <div />
                                )}
                                <div className="flex gap-2 flex-wrap justify-end">
                                    {test.test_type === "Вопросно-ответная форма" && (
                                        <button
                                            type="button"
                                            onClick={() => copyLink(test.id)}
                                            data-testid={`copy-prof-link-${test.id}`}
                                            className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 font-medium text-slate-700"
                                            title="Скопировать ссылку для прохождения"
                                        >
                                            {copiedId === test.id ? "Скопировано" : "Скопировать ссылку"}
                                        </button>
                                    )}
                                    <button 
                                        onClick={() => onTestClick(test)} 
                                        className="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 text-[#cda834] rounded-lg hover:bg-yellow-50 hover:border-yellow-200 transition-all shadow-sm"
                                        title="Просмотр"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                                    </button>
                                    {onTestEdit && (
                                        <button 
                                            onClick={() => onTestEdit(test)} 
                                            className="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 text-slate-500 hover:text-slate-900 rounded-lg hover:bg-slate-50 transition-all shadow-sm"
                                            title="Редактировать"
                                        >
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                                        </button>
                                    )}
                                    <button 
                                        onClick={() => onTestDeleted(test.id)} 
                                        className="w-8 h-8 flex items-center justify-center bg-white border border-red-200 text-red-500 hover:text-red-700 rounded-lg hover:bg-red-50 transition-all shadow-sm"
                                        title="Удалить"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );

    return (
        <div>
            {renderTestGroup(professionalTests, "Профессиональные тесты")}
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-4">
                    <h2 className="text-xl font-bold text-slate-900">Психологические тесты</h2>
                </div>
                {psychCatalog}
                {legacyPsych.length > 0 && (
                    <div className="mt-6">{renderTestGroup(legacyPsych, null)}</div>
                )}
            </div>
        </div>
    );
}
