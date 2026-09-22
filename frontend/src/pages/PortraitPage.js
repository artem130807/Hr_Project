import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import MainLayout from "../layout/MainLayout";
import PortraitForm from "../components/portrait/PortraitForm";
import {
    getCompanyCandidateImage,
    createCompanyCandidateImage,
    updateCompanyCandidateImage,
    getDepartmentCandidateImage,
    createDepartmentCandidateImage,
    updateDepartmentCandidateImage
} from "../services/candidateImageApi";
import { useAlertContext } from "../context/AlertContext";
import { isLeaderRole } from "../config/navConfig";

export default function PortraitPage() {
    const { user } = useAuth();
    const [portrait, setPortrait] = useState(null);
    const rawCompanyId =
        user?.company_id ??
        user?.companyId ??
        user?.company?.id ??
        user?.company?.company_id ??
        portrait?.company_id ??
        portrait?.company?.id ??
        null;
    const companyId = rawCompanyId != null && rawCompanyId !== "" ? Number(rawCompanyId) : NaN;
    const [loading, setLoading] = useState(true);
    const [isEditing, setIsEditing] = useState(false);
    const {showAlert} = useAlertContext()

    const isOwner = user.role === "owner" || user.role === "dev";
    const isLead = user.role === "lead" || isLeaderRole(user.role);

    const department =
        user?.department ??
        user?.profile?.department ??
        user?.department_name ??
        user?.team ??
        null;

    const fetchPortrait = async () => {
        try {
            setLoading(true);
            let data;

            if (isOwner) {
                try {
                    data = await getCompanyCandidateImage();
                } catch (err) {
                    const msg = String(err?.message || "");
                    if (!msg.includes("404") && !msg.toLowerCase().includes("not found")) throw err;
                }
            } else if (isLead) {
                if (department) {
                    try {
                        data = await getDepartmentCandidateImage(department);
                    } catch (err) {
                        const msg = String(err?.message || "");
                        if (!msg.includes("404") && !msg.toLowerCase().includes("not found")) throw err;
                    }
                } else {
                    console.warn("Портрет отдела: не удалось определить department у пользователя");
                }
            }

            setPortrait(data || null);
        } catch (e) {
            const msg = String(e?.message || "");
            if (!msg.includes("404") && !msg.toLowerCase().includes("not found")) {
                console.error("Ошибка загрузки портрета:", e);
                showAlert(`Ошибка загрузки портрета: ${e.message}`, "error");
            }
            setPortrait(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPortrait();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.id, user?.role]);

    const handleSave = async (formData) => {
        try {
            if (portrait?.id) {
                if (isOwner) {
                    await updateCompanyCandidateImage(formData);
                } else if (isLead) {
                    await updateDepartmentCandidateImage(department, formData);
                }
            } else {
                if (isOwner) {
                    if (Number.isNaN(companyId)) {
                        const fallback = String(rawCompanyId ?? "").trim();
                        if (fallback) {
                            await createCompanyCandidateImage({ ...formData, company_id: fallback });
                        } else {
                            await createCompanyCandidateImage(formData);
                        }
                    } else {
                        await createCompanyCandidateImage({ ...formData, company_id: String(companyId) });
                    }
                } else if (isLead) {
                    const leadId = String(user.erp_user_id || user.id || "");
                    if (!leadId) {
                        showAlert("Ошибка: не удалось определить ID пользователя", "error");
                        return;
                    }
                    await createDepartmentCandidateImage({
                        ...formData,
                        lead_id: leadId,
                        ...(department ? { department } : {}),
                    });
                }
            }
            await fetchPortrait();
            setIsEditing(false);
            showAlert("Портрет сохранён", "success")
        } catch (e) {
            showAlert(`Ошибка сохранения: ${e.message}`, "error")
        }
    };


    if (loading) return <MainLayout><p>Загрузка...</p></MainLayout>;

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <div className="mb-6 space-y-6">
                <div className="flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Портрет кандидата</h1>
                        <p className="mt-1 text-sm text-slate-500">
                            {isOwner ? "Идеальный кандидат для всей компании" : `Идеальный кандидат для вашего отдела: ${department || ""}`}
                        </p>
                    </div>
                </div>
            </div>

            {!portrait && !isEditing ? (
                <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <h3 className="text-lg font-medium text-slate-800">Портрет ещё не создан</h3>
                    <p className="text-slate-500 mt-1 mb-6">Опишите идеального кандидата, чтобы HR-отдел понимал, кого вы ищете.</p>
                    <button
                        onClick={() => setIsEditing(true)}
                        className="bg-slate-900 text-white px-6 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                        Создать портрет
                    </button>
                </div>
            ) : isEditing ? (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 p-6">
                    <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-100">
                        <h2 className="text-xl font-bold text-slate-900">
                            {portrait ? "Редактировать портрет" : "Создание портрета"}
                        </h2>
                        {portrait && (
                            <button onClick={() => setIsEditing(false)} className="text-slate-400 hover:text-slate-600 transition-colors">
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                        )}
                    </div>
                    <PortraitForm initialData={portrait} onSave={handleSave} isCompany={isOwner} />
                </div>
            ) : (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-hidden">
                    <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                            </div>
                            <div>
                                <h2 className="text-lg font-bold text-slate-900">Текущий профиль кандидата</h2>
                                <p className="text-sm text-slate-500">{isOwner ? "Для всей компании" : `Для отдела ${department}`}</p>
                            </div>
                        </div>
                        <button
                            onClick={() => setIsEditing(true)}
                            className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-xl hover:bg-slate-50 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
                        >
                            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                            Редактировать
                        </button>
                    </div>

                    <div className="p-6 grid gap-6 md:grid-cols-2">
                        {isOwner ? (
                            <>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" /></svg>
                                        Гибкие навыки
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.soft_skills || "Не указаны"}</p>
                                </div>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>
                                        Ценности
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.values || "Не указаны"}</p>
                                </div>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100 md:col-span-2">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                        Красные флаги
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.red_flags || "Не указаны"}</p>
                                </div>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100 md:col-span-2">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                                        Общие требования
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.common_requirements || "Не указаны"}</p>
                                </div>
                            </>
                        ) : (
                            <>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                                        Профессиональные навыки
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.hard_skills || "Не указаны"}</p>
                                </div>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                        Опыт работы
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.expirience || portrait.experience || "Не указано"}</p>
                                </div>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100 md:col-span-2">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                                        Общие требования
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.common_requirements || "Не указаны"}</p>
                                </div>
                                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100 md:col-span-2">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
                                        Специфика работы
                                    </h3>
                                    <p className="text-slate-700 whitespace-pre-wrap">{portrait.specifics || "Не указана"}</p>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}
        </MainLayout>
    );
}