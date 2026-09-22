import { useEffect, useRef, useState } from "react";

export default function OfferModal({ open, defaultText = "", onClose, onSubmit }) {
    const [text, setText] = useState(defaultText || "");
    const [loading, setLoading] = useState(false);
    const [includeDocuments, setIncludeDocuments] = useState(false);
    const textareaRef = useRef(null);

    useEffect(() => {
        if (open) {
            setText(defaultText || "");
            setIncludeDocuments(false);
            setTimeout(() => textareaRef.current?.focus(), 0);
        }
    }, [open, defaultText]);

    if (!open) return null;

    const handleSubmit = async () => {
        const val = text.trim();
        if (!val) return;
        try {
            setLoading(true);
            await onSubmit?.(val, includeDocuments);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 no-click-open">
            <div
                className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
                onClick={() => (!loading ? onClose?.() : null)}
            />
            <div className="relative z-10 w-full max-w-xl bg-white rounded-2xl shadow-2xl ring-1 ring-slate-900/5 overflow-hidden">
                <div className="px-6 py-5 border-b border-slate-100">
                    <h3 className="text-lg font-semibold text-slate-900">Отправить оффер</h3>
                    <p className="mt-1 text-sm text-slate-500">Проверьте текст и отправьте кандидату.</p>
                </div>
                <div className="p-6">
                    <label className="block text-xs font-medium uppercase tracking-wide text-slate-400 mb-2">
                        Текст письма
                    </label>
                    <textarea
                        ref={textareaRef}
                        className="w-full min-h-[180px] border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#cda834]/40 focus:border-[#cda834]"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder="Введите текст оффера…"
                    />
                    <label className="mt-4 flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                        <input type="checkbox" className="mt-0.5" checked={includeDocuments} onChange={(event) => setIncludeDocuments(event.target.checked)} />
                        <span><b className="block">Приложить ссылку для документов</b><span className="text-slate-500">Кандидат получит персональную форму для загрузки документов на трудоустройство.</span></span>
                    </label>
                    <div className="mt-4 flex justify-end gap-2">
                        <button
                            type="button"
                            className="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 text-sm font-medium"
                            onClick={() => (!loading ? onClose?.() : null)}
                            disabled={loading}
                        >
                            Отмена
                        </button>
                        <button
                            type="button"
                            className="px-4 py-2 rounded-xl bg-[#e0bb48] text-slate-900 hover:bg-[#d4af3a] text-sm font-semibold disabled:opacity-60"
                            onClick={handleSubmit}
                            disabled={loading || !text.trim()}
                        >
                            {loading ? "Отправка…" : "Отправить оффер"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
