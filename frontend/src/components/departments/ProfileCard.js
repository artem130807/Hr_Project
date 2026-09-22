import { useState } from "react";

export default function ProfileCard({ profile, onDelete, onEdit }) {
    const [showConfirm, setShowConfirm] = useState(false);

    const handleDelete = async () => {
        if (typeof onDelete === "function") {
            await onDelete(profile);
        }
        setShowConfirm(false);
    };

    return (
        <div className="border p-4 rounded shadow relative">
            <h3 className="text-xl font-bold mb-2">{profile.title || profile.department || `Профиль #${profile.id}`}</h3>
            <p><strong>Навыки:</strong> {profile.skills || profile.hard_skills || "—"}</p>
            <p><strong>Опыт:</strong> {profile.experience || profile.expirience || "—"}</p>
            <p><strong>Инструменты:</strong> {profile.tools || "—"}</p>
            <p><strong>KPI:</strong> {profile.kpi || "—"}</p>

            <div className="mt-4 flex space-x-2">
                <button onClick={onEdit} className="bg-yellow-500 text-white px-3 py-1 rounded">Редактировать</button>
                <button onClick={() => setShowConfirm(true)} className="bg-red-500 text-white px-3 py-1 rounded">Удалить</button>
            </div>

            {showConfirm && (
                <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center z-10">
                    <div className="bg-white p-4 rounded shadow-lg w-72 text-center">
                        <p className="mb-4 text-lg">Удалить профиль?</p>
                        <div className="flex justify-center space-x-4">
                            <button
                                onClick={handleDelete}
                                className="bg-red-600 text-white px-4 py-1 rounded"
                            >
                                Да
                            </button>
                            <button
                                onClick={() => setShowConfirm(false)}
                                className="bg-gray-300 px-4 py-1 rounded"
                            >
                                Нет
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
