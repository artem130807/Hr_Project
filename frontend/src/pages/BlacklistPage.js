import {useEffect, useState} from "react";
import {getBlackListedCandidates, unblockCandidate} from "../services/blacklistApi";
import {useAlertContext} from "../context/AlertContext";
import MainLayout from "../layout/MainLayout";

export default function BlacklistPage() {
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(true);
    const {showAlert} = useAlertContext();

    const fetchBlacklist = async () => {
        try {
            setLoading(true);
            const data = await getBlackListedCandidates();
            setCandidates(Array.isArray(data) ? data : []);
        } catch (e) {
            console.error("Ошибка загрузки черного списка", e)
            showAlert("Ошибка загрузки черного списка", "error")
            setCandidates([])
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        fetchBlacklist();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const handleUnblock = async (candidateId, candidateName) => {
        if(!window.confirm(`Вернуть ${candidateName} из черного списка?`)) return;

        try {
            await unblockCandidate(candidateId)
            showAlert("Кандидат возвращен из черного списка", "success")
            fetchBlacklist()
        } catch (e) {
            console.error('Ошибка', e)
            showAlert(`Ошибка ${e.message}`, "error")
        }
    }

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <div className="mb-6 space-y-6">
                <div className="flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Черный список</h1>
                        <p className="mt-1 text-sm text-slate-500">Кандидаты, занесенные в черный список, и причины блокировки.</p>
                    </div>
                </div>

                {loading ? (
                    <div className="flex justify-center items-center py-20 text-slate-400">
                        <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Загрузка...
                    </div>
                ) : candidates.length === 0 ? (
                    <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                        <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                        </div>
                        <h3 className="text-lg font-medium text-slate-800">Черный список пуст</h3>
                        <p className="text-slate-500 mt-1">Здесь будут отображаться заблокированные кандидаты.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {candidates.map(candidate => (
                            <div key={candidate.id} className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200/60 relative overflow-hidden group flex flex-col h-full">
                                <div className="absolute top-0 left-0 w-1 h-full bg-red-400"></div>
                                <div className="flex-1 pl-2">
                                    <h3 className="text-lg font-bold text-slate-900 mb-1 truncate" title={candidate.full_name}>{candidate.full_name}</h3>
                                    
                                    <div className="space-y-1 mb-4">
                                        {candidate.email && (
                                            <p className="text-sm text-slate-500 flex items-center gap-2">
                                                <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                                                {candidate.email}
                                            </p>
                                        )}
                                        {(candidate.phone_number || candidate.phone) && (
                                            <p className="text-sm text-slate-500 flex items-center gap-2">
                                                <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                                                {candidate.phone_number || candidate.phone}
                                            </p>
                                        )}
                                    </div>

                                    {candidate.blacklist_reason &&(
                                        <div className="mb-4 bg-red-50/50 border border-red-100 p-3 rounded-xl flex items-start gap-2">
                                            <svg className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                            <p className="text-sm text-red-800">
                                                {candidate.blacklist_reason}
                                            </p>
                                        </div>
                                    )}
                                </div>

                                <button 
                                    onClick={() => handleUnblock(candidate.id, candidate.full_name)} 
                                    className="w-full bg-white border border-slate-200 text-slate-700 px-4 py-2.5 rounded-xl hover:bg-slate-50 transition-colors shadow-sm text-sm font-medium mt-auto"
                                >
                                    Вернуть из ЧС
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </MainLayout>
    )
}