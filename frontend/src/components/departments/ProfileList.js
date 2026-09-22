export default function ProfileList({profiles, onEdit}) {
    if(!profiles || profiles.length === 0) {
        return (
            <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
                </div>
                <h3 className="text-lg font-medium text-slate-800">Профили отделов пока не созданы</h3>
                <p className="text-slate-500 mt-1 max-w-md">Выберите отдел из списка и создайте для него профиль идеального кандидата.</p>
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {profiles.map((profile, idx) => (
                <div key={profile.id || idx} className="bg-white rounded-2xl shadow-sm border border-slate-200/60 hover:shadow-md transition-all duration-300 flex flex-col overflow-hidden">
                    <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-sm shrink-0 border border-blue-200/50">
                            {profile.department ? profile.department.charAt(0).toUpperCase() : "О"}
                        </div>
                        <div className="min-w-0">
                            <h3 className="text-lg font-bold text-slate-900 leading-tight truncate">
                                Отдел: {profile.department || "Без названия"}
                            </h3>
                            {profile.lead_id ? (
                            <p className="text-xs font-medium text-slate-500 mt-0.5">
                                Руководитель ID: {profile.lead_id}
                            </p>
                            ) : null}
                        </div>
                    </div>

                    <div className="p-6 flex-1 space-y-5">
                        <div>
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                                Профессиональные навыки
                            </h4>
                            <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100">
                                {profile.hard_skills || <span className="text-slate-400 italic">Не указаны</span>}
                            </p>
                        </div>

                        <div>
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                Опыт работы
                            </h4>
                            <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100">
                                {profile.expirience || profile.experience || <span className="text-slate-400 italic">Не указан</span>}
                            </p>
                        </div>

                        <div>
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                                Общие требования / Специфика
                            </h4>
                            <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100">
                                {profile.common_requirements || profile.work_specificity || <span className="text-slate-400 italic">Не указаны</span>}
                            </p>
                        </div>
                    </div>
                    {onEdit && (
                        <div className="px-6 pb-6">
                            <button
                                type="button"
                                onClick={() => onEdit(profile)}
                                className="text-sm font-medium text-slate-700 hover:text-slate-900"
                            >
                                Редактировать
                            </button>
                        </div>
                    )}
                </div>
            ))}
        </div>
    )
}