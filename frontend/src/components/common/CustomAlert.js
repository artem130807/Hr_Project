import {useEffect} from "react";

export default function CustomAlert({message, type = "info", onClose}) {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose();
        }, 3000);
        return () => clearTimeout(timer);
    }, [onClose]);

    const colors = {
        success: "bg-green-100 border-green-500 text-green-700",
        error: "bg-red-100 border-red-500 text-red-700",
        warning: "bg-yellow-100 border-yellow-500 text-yellow-700",
        info: "bg-blue-100 border-blue-500 text-blue-700",
    };

    const icons = {
        success: "✓",
        error: "✕",
        warning: "⚠",
        info: "ℹ",
    };

    return (
        <div className={`border-l-4 px-4 py-3 rounded shadow-lg min-w-[280px] max-w-[420px] animate-slide-in ${colors[type] || colors.info}`}>
            <div className="flex items-start">
                <span className="text-xl mr-3 leading-none">{icons[type] || icons.info}</span>
                <div className="flex-1">
                    <p className="font-medium text-sm">{message}</p>
                </div>
                <button
                    type="button"
                    onClick={onClose}
                    className="ml-3 text-lg font-bold hover:opacity-70 leading-none"
                    aria-label="Закрыть"
                >
                    ×
                </button>
            </div>
        </div>
    );
}
