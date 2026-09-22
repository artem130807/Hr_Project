import { useState, useEffect } from "react";
import { getCandidateActiveVacancy } from "../../services/candidateApi";
import { relationVacancyName } from "../../utils/candidateMapper";
import { formatDateRu } from "../../utils/dateFormat";

export default function CandidateCard({ candidate }) {
    const [activeVacancy, setActiveVacancy] = useState(null);

    useEffect(() => {
        if (!candidate?.id) return;

        getCandidateActiveVacancy(candidate.id)
            .then(data => setActiveVacancy(data))
            .catch(() => setActiveVacancy(null));
    }, [candidate?.id]);

    return (
        <div className="bg-white rounded shadow p-4 hover:shadow-md transition">
            {candidate.photo_url && (
                <img
                    src={candidate.photo_url}
                    alt={candidate.full_name}
                    className="w-full h-48 object-cover rounded mb-4"
                />
            )}
            <h2 className="text-lg font-semibold">{candidate.full_name}</h2>
            <p className="text-sm text-gray-600">Пол: {candidate.gender}</p>
            <p className="text-sm text-gray-600">Дата рождения: {formatDateRu(candidate.birthdate)}</p>
            <p className="text-sm text-gray-600">Образование: {candidate.education}</p>
            <p className="text-sm text-gray-600">Опыт: {candidate.experience}</p>
            <p className="text-sm text-gray-600">Навыки: {candidate.skills}</p>
            {candidate.created_at && (
                <p className="text-sm text-gray-600">Добавлен: {new Date(candidate.created_at).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}</p>
            )}

            <div className="mt-2 flex items-center gap-2">
                <span className="text-xs font-semibold text-purple-700">
                    🤖 AI: {candidate.ai_score !== null && candidate.ai_score !== undefined ? `${candidate.ai_score.toFixed(0)}/100` : "Нет оценки"}
                </span>
            </div>

            {activeVacancy && (
                <div className="mt-2">
                    <span className="inline-block px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                        📋 {relationVacancyName(activeVacancy) || "Вакансия"}
                    </span>
                </div>
            )}

            {(candidate.status || candidate.current_status) && (
                <span className="mt-2 inline-block px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium">{candidate.status || candidate.current_status}</span>
            )}

            {candidate.stage && (
                <p className={`mt-2 ml-2 inline-block text-xs px-2 py-1 rounded font-medium ${
                    candidate.stage === "нанят" ? "bg-green-100 text-green-800" :
                        candidate.stage === "в процессе найма" ? "bg-blue-100 text-blue-800" :
                            candidate.stage === "архивирован" ? "bg-gray-100 text-gray-800" :
                                candidate.stage === "в черном списке" ? "bg-red-100 text-red-800" :
                                    "bg-gray-100 text-gray-800"
                }`}>
                    {candidate.stage}
                </p>
            )}
        </div>
    );
}