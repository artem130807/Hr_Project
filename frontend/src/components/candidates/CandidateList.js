import {
    sendOffer,
    applyCandidateStatus,
    updateCandidate,
    sendInterviewInvite,
} from "../../services/candidateApi";
import {useAlertContext} from "../../context/AlertContext";
import {useAuth} from "../../context/AuthContext";
import {useState} from "react";
import OfferModal from "./OfferModal";
import InterviewInviteModal from "./InterviewInviteModal";
import CandidateQuickActions from "./CandidateQuickActions";
import ExerciseModal from "../calendar/ExerciseModal";
import InterviewReminderModal from "../calendar/InterviewReminderModal";
import { experienceLabel, genderLabel } from "../../utils/hhLabels";
import { telegramHref } from "../../utils/candidateMapper";
import { isArchiveStatus, statusLabel } from "../../utils/candidateStatuses";
import { buildOfferLetterText } from "../../utils/interviewInvite";
import { HR_INTERVIEW_REMINDER_QUESTION } from "../../utils/interviewReminder";

export default function CandidateList({
    candidates,
    onCandidateDelete,
    onCandidateEdit,
    onCandidateClick,
    lastCandidateRef,
    onChange,
    isArchiveView = false,
}) {
    const {showAlert} = useAlertContext();
    const {user} = useAuth() || {};
    const [offerOpen, setOfferOpen] = useState(false);
    const [interviewOpen, setInterviewOpen] = useState(false);
    const [selectedCandidate, setSelectedCandidate] = useState(null);
    const [commentEditId, setCommentEditId] = useState(null);
    const [commentText, setCommentText] = useState("");
    const [commentSaving, setCommentSaving] = useState(false);
    const [localComments, setLocalComments] = useState({});
    const [testModalOpen, setTestModalOpen] = useState(false);
    const [selectedTestCandidate, setSelectedTestCandidate] = useState(null);
    const [reminderCandidate, setReminderCandidate] = useState(null);
    const [reminderSchedule, setReminderSchedule] = useState(null);

    const [busyId, setBusyId] = useState(null);
    const [localStatuses, setLocalStatuses] = useState({});

    const openProfessionalTestModal = (candidate) => {
        setSelectedTestCandidate(candidate);
        setTestModalOpen(true);
    };

    const closeProfessionalTestModal = () => {
        setTestModalOpen(false);
        setSelectedTestCandidate(null);
    };

    const submitOffer = async (offerText, includeDocumentsLink = false) => {
        if(!selectedCandidate) return;

        try {
            await sendOffer(selectedCandidate.id, offerText, includeDocumentsLink);
            setOfferOpen(false);
            setSelectedCandidate(null);
            showAlert("Оффер отправлен", "success");
            onChange?.();
        } catch (e) {
            const raw = e?.message || e;
            let msg = typeof raw === "string" ? raw : "";

            if (!msg && raw && typeof raw === "object" && raw.detail) {
                msg = raw.detail;
            }
            if (!msg) {
                try { msg = JSON.stringify(raw); } catch(_) { msg = "Unknown error"; }
            }

            showAlert(`Ошибка отправки оффера: ${msg}`, "error");
        }
    };

    const templateWithCandidateName = buildOfferLetterText(selectedCandidate?.full_name);

    const notifyInterviewResult = (resp) => {
        if (resp?.delivery && resp.delivery !== "sent" && resp.delivery !== "ok") {
            showAlert(
                resp?.warning || "Собеседование сохранено, но HH пока не принял приглашение.",
                "warning"
            );
        } else {
            showAlert("Приглашение на собеседование отправлено кандидату в HH", "success");
        }
    };

    const submitInterviewInvite = async (message, schedule, reminder) => {
        if (!selectedCandidate?.id) return;
        try {
            const hrId = user?.erp_user_id || user?.id;
            const resp = await sendInterviewInvite(selectedCandidate.id, {
                message,
                hr_id: hrId || null,
                interview_date: schedule?.date,
                start_time: schedule?.startTime,
                end_time: schedule?.endTime,
                book_calendar: Boolean(hrId && schedule?.date && schedule?.startTime),
                remind_candidate: Boolean(reminder?.enabled),
                remind_at: reminder?.remind_at || null,
                reminder_message: reminder?.message || null,
            });
            notifyInterviewResult(resp);
            setLocalStatuses((prev) => ({ ...prev, [selectedCandidate.id]: "собес" }));
            const invited = selectedCandidate;
            setInterviewOpen(false);
            setSelectedCandidate(null);
            onChange?.();
            const wantReminder = window.confirm(HR_INTERVIEW_REMINDER_QUESTION);
            if (wantReminder) {
                setReminderCandidate(invited);
                setReminderSchedule(schedule || null);
            }
        } catch (e) {
            showAlert(`Ошибка отправки приглашения: ${e?.message || e}`, "error");
            throw e;
        }
    };

    const closeInterviewReminder = () => {
        setReminderCandidate(null);
        setReminderSchedule(null);
    };

    const handleQuickStatus = async (candidate, nextStatus) => {
        if (!candidate?.id || String(candidate.status || localStatuses[candidate.id] || "").trim() === nextStatus) {
            return;
        }
        if (nextStatus === "отказ") {
            const ok = window.confirm(
                `Отказать кандидату ${candidate.full_name || ""}? Карточка будет переведена в архив.`
            );
            if (!ok) return;
        }
        try {
            setBusyId(candidate.id);
            await applyCandidateStatus(candidate.id, nextStatus);
            setLocalStatuses((prev) => ({ ...prev, [candidate.id]: nextStatus }));
            const message =
                nextStatus === "собес"
                    ? "Кандидат приглашён на собеседование"
                    : nextStatus === "подумать"
                      ? "Кандидат отложен — статус «Подумать»"
                      : "Кандидату отказано, карточка в архиве";
            showAlert(message, "success");
            if (isArchiveStatus(nextStatus)) {
                onChange?.();
            }
        } catch (e) {
            const msg = e?.message || String(e);
            if (/active vacancy not found|Active vacancy/i.test(msg)) {
                showAlert("Сначала привяжите кандидата к вакансии — затем можно сменить статус.", "warning");
            } else {
                showAlert(`Не удалось обновить статус: ${msg}`, "error");
            }
        } finally {
            setBusyId(null);
        }
    };

    const handleCommentSave = async (candidateId) => {
        try {
            setCommentSaving(true);
            await updateCandidate(candidateId, { hr_comment: commentText || null });
            setLocalComments(prev => ({ ...prev, [candidateId]: commentText }));
            setCommentEditId(null);
            showAlert("Комментарий сохранён", "success");
        } catch (e) {
            showAlert(`Ошибка сохранения: ${e.message}`, "error");
        } finally {
            setCommentSaving(false);
        }
    };

    if(!candidates || candidates.length === 0) {
        return null; // Handled in parent
    }

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {candidates.map((candidate, idx) => {
            const isLast = idx === candidates.length - 1;
            const currentComment = localComments[candidate.id] !== undefined ? localComments[candidate.id] : (candidate.hr_comment || "");
            const currentStatus = localStatuses[candidate.id] || candidate.status;
            const statusTitle = statusLabel(currentStatus) || "Нет статуса";
            const activeVacancyName =
                candidate.vacancy_name
                || candidate.last_vacancy_title
                || candidate.position
                || "Позиция не указана";
            
            return (
                <div 
                    key={candidate.id} 
                    ref={isLast ? lastCandidateRef : null} 
                    className="bg-white rounded-2xl shadow-sm border border-slate-200/60 hover:shadow-md transition-all duration-300 flex flex-col group cursor-pointer"
                    onClick={(e) => {
                        // ignore clicks from inner inputs/buttons
                        if (e.target.closest('button') || e.target.closest('input') || e.target.closest('select') || e.target.closest('.no-click-open')) {
                            return;
                        }
                        onCandidateClick?.(candidate);
                    }}
                >
                    <div className="p-6 flex-1">
                        <div className="flex justify-between items-start mb-4 gap-4">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 font-bold text-lg border border-slate-200 shadow-sm shrink-0">
                                    {candidate.full_name ? candidate.full_name.charAt(0).toUpperCase() : "К"}
                                </div>
                                <div>
                                    <h3 className="font-bold text-lg text-slate-900 group-hover:text-blue-600 transition-colors leading-tight">{candidate.full_name || "Без имени"}</h3>
                                    <div className="text-sm font-medium text-slate-500 mt-1 truncate max-w-[200px]" title={activeVacancyName}>
                                        {activeVacancyName}
                                    </div>
                                </div>
                            </div>
                            <span
                                className={`shrink-0 px-2.5 py-1 rounded-lg text-xs font-medium max-w-[140px] truncate text-center border ${
                                    currentStatus === "собес"
                                        ? "bg-sky-50 text-sky-800 border-sky-200"
                                        : currentStatus === "подумать"
                                          ? "bg-amber-50 text-amber-900 border-amber-200"
                                          : currentStatus === "отказ"
                                            ? "bg-rose-50 text-rose-800 border-rose-200"
                                            : "bg-slate-50 text-slate-600 border-slate-200/60"
                                }`}
                                title={statusTitle}
                            >
                                {statusTitle}
                            </span>
                        </div>

                        <div className="space-y-2.5 text-sm text-slate-600 mb-5 pl-16">
                            {candidate.next_contact_at ? (
                                <div className={`rounded-lg border px-2.5 py-2 text-xs ${
                                    new Date(candidate.next_contact_at).getTime() <= Date.now()
                                        ? "border-rose-200 bg-rose-50 text-rose-700"
                                        : "border-amber-200 bg-amber-50 text-amber-800"
                                }`}>
                                    <b>{new Date(candidate.next_contact_at).getTime() <= Date.now() ? "Пора связаться" : "Следующий контакт"}</b>
                                    {`: ${new Date(candidate.next_contact_at).toLocaleString("ru-RU")}`}
                                    {candidate.next_contact_owner_name ? ` · ${candidate.next_contact_owner_name}` : ""}
                                </div>
                            ) : null}
                            {(candidate.phone_number || candidate.email || candidate.telegram_username) && (
                                <div className="space-y-1">
                                    {candidate.phone_number && (
                                        <div className="flex items-center gap-2">
                                            <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                                            <span>{candidate.phone_number}</span>
                                        </div>
                                    )}
                                    {candidate.email && (
                                        <div className="flex items-center gap-2">
                                            <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                                            <a
                                                href={`mailto:${candidate.email}`}
                                                className="truncate text-sky-700 hover:underline"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                {candidate.email}
                                            </a>
                                        </div>
                                    )}
                                    {candidate.telegram_username && (
                                        <div className="flex items-center gap-2">
                                            <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
                                            {telegramHref(candidate.telegram_username) ? (
                                                <a
                                                    href={telegramHref(candidate.telegram_username)}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="text-sky-700 hover:underline"
                                                    onClick={(e) => e.stopPropagation()}
                                                >
                                                    {candidate.telegram_username}
                                                </a>
                                            ) : (
                                                <span>{candidate.telegram_username}</span>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}

                            {(candidate.salary_expectations || candidate.gender || candidate.total_experience) && (
                                <div className="flex flex-wrap gap-x-4 gap-y-2 pt-2 text-xs font-medium text-slate-500">
                                    {candidate.salary_expectations > 0 && (
                                        <div className="flex items-center gap-1.5 bg-slate-50 px-2 py-1 rounded border border-slate-100">
                                            <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                            {candidate.salary_expectations.toLocaleString("ru-RU")} ₽
                                        </div>
                                    )}
                                    {candidate.gender && (
                                        <div className="flex items-center gap-1 bg-slate-50 px-2 py-1 rounded border border-slate-100">
                                            {genderLabel(candidate.gender)}
                                        </div>
                                    )}
                                    {candidate.total_experience && (
                                        <div className="flex items-center gap-1 bg-slate-50 px-2 py-1 rounded border border-slate-100">
                                            Опыт: {experienceLabel(candidate.total_experience)}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {commentEditId === candidate.id ? (
                            <div className="pl-16 mb-4 no-click-open">
                                <textarea
                                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all resize-none mb-2"
                                    rows="2"
                                    value={commentText}
                                    onChange={(e) => setCommentText(e.target.value)}
                                    placeholder="Оставьте комментарий..."
                                />
                                <div className="flex justify-end gap-2">
                                    <button 
                                        type="button"
                                        onClick={() => setCommentEditId(null)}
                                        className="px-3 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                                    >
                                        Отмена
                                    </button>
                                    <button 
                                        type="button"
                                        onClick={() => handleCommentSave(candidate.id)}
                                        disabled={commentSaving}
                                        className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors shadow-sm disabled:opacity-50"
                                    >
                                        {commentSaving ? "..." : "Сохранить"}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="pl-16 mb-4 no-click-open">
                                <div 
                                    onClick={() => {
                                        setCommentText(currentComment);
                                        setCommentEditId(candidate.id);
                                    }}
                                    className="px-3 py-2 text-sm bg-yellow-50/50 text-yellow-800 rounded-xl border border-yellow-100 hover:bg-yellow-50 transition-colors cursor-text min-h-[40px] flex items-center relative group/comment"
                                >
                                    {currentComment ? (
                                        <span className="block truncate pr-6">{currentComment}</span>
                                    ) : (
                                        <span className="text-yellow-600/50 italic flex items-center gap-1">
                                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                            Добавить комментарий...
                                        </span>
                                    )}
                                    {currentComment && (
                                        <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover/comment:opacity-100 transition-opacity">
                                            <svg className="w-4 h-4 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="p-4 border-t border-slate-100 bg-slate-50/50 rounded-b-2xl no-click-open space-y-3">
                        <CandidateQuickActions
                            candidate={{ ...candidate, status: currentStatus }}
                            busy={busyId === candidate.id}
                            isArchiveView={isArchiveView}
                            onStatus={handleQuickStatus}
                            onInterview={(item) => {
                                setSelectedCandidate(item);
                                setInterviewOpen(true);
                            }}
                            onOffer={(item) => {
                                setSelectedCandidate(item);
                                setOfferOpen(true);
                            }}
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                type="button"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    openProfessionalTestModal(candidate);
                                }}
                                className="px-3 shrink-0 flex items-center justify-center bg-white border border-indigo-200 text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 py-2 rounded-xl transition-colors shadow-sm text-xs font-semibold"
                                title="Отправить профессиональный тест"
                            >
                                Отправить тест
                            </button>
                            <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); onCandidateEdit(candidate); }}
                                className="w-10 shrink-0 flex items-center justify-center bg-white border border-slate-200 text-slate-500 hover:text-slate-700 hover:bg-slate-50 py-2 rounded-xl transition-colors shadow-sm"
                                title="Редактировать"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                            </button>
                            <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); onCandidateDelete(candidate.id); }}
                                className="w-10 shrink-0 flex items-center justify-center bg-white border border-red-200 text-red-500 hover:text-red-700 hover:bg-red-50 py-2 rounded-xl transition-colors shadow-sm"
                                title="Удалить"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                            </button>
                        </div>
                    </div>
                </div>
            )})}
            
            <OfferModal
                open={offerOpen && Boolean(selectedCandidate)}
                defaultText={templateWithCandidateName}
                onClose={() => {
                    setOfferOpen(false);
                    setSelectedCandidate(null);
                }}
                onSubmit={submitOffer}
            />
            <InterviewInviteModal
                open={interviewOpen && Boolean(selectedCandidate)}
                candidate={selectedCandidate}
                onClose={() => {
                    setInterviewOpen(false);
                    setSelectedCandidate(null);
                }}
                onSubmit={submitInterviewInvite}
            />
            <InterviewReminderModal
                open={Boolean(reminderCandidate)}
                candidate={reminderCandidate}
                date={reminderSchedule?.date || ""}
                startTime={reminderSchedule?.startTime || ""}
                endTime={reminderSchedule?.endTime || ""}
                onClose={closeInterviewReminder}
                onSkip={closeInterviewReminder}
                onSaved={closeInterviewReminder}
            />
            {testModalOpen && selectedTestCandidate ? (
                <ExerciseModal
                    candidate={selectedTestCandidate}
                    onClose={closeProfessionalTestModal}
                    onSuccess={() => {
                        closeProfessionalTestModal();
                        onChange?.();
                    }}
                />
            ) : null}
        </div>
    );
}
