import {useState, useEffect} from "react";
import {bookSlot} from "../../services/sheduleApi";
import {getCandidate, getCandidates, sendInterviewInvite} from "../../services/candidateApi";
import InterviewInviteModal from "../candidates/InterviewInviteModal";
import InterviewReminderModal from "./InterviewReminderModal";
import {useAuth} from "../../context/AuthContext";
import {useAlertContext} from "../../context/AlertContext";
import { formatDateRu } from "../../utils/dateFormat";
import { HR_INTERVIEW_REMINDER_QUESTION } from "../../utils/interviewReminder";

export default function BookingModal({slot, onClose, onSuccess, onDeleteSlot}) {
    const [candidates, setCandidates] = useState([]);
    const [selectedCandidateId, setSelectedCandidateId] = useState("");
    const [search, setSearch] = useState("");
    const [loading, setLoading] = useState(false);
    const [loadingCandidates, setLoadingCandidates] = useState(true);
    const [inviteCandidate, setInviteCandidate] = useState(null);
    const [reminderCandidate, setReminderCandidate] = useState(null);
    const {showAlert} = useAlertContext();
    const {user} = useAuth() || {};

    useEffect(() => {
        let cancelled = false;
        const timer = setTimeout(async () => {
            try {
                setLoadingCandidates(true);
                // One page only — avoid flooding API (was up to 20×100 requests)
                const data = await getCandidates(
                    null,
                    search.trim() || null,
                    null,
                    null,
                    undefined,
                    0,
                    50
                );
                if (cancelled) return;
                const items = Array.isArray(data) ? data : (data?.items ?? []);
                setCandidates(items);
            } catch (e) {
                if (!cancelled) {
                    showAlert(`Ошибка загрузки кандидатов: ${e.message || e}`, "error");
                    setCandidates([]);
                }
            } finally {
                if (!cancelled) setLoadingCandidates(false);
            }
        }, search ? 300 : 0);

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [search, showAlert]);

    const askHrReminder = (candidate) => {
        const wantReminder = window.confirm(HR_INTERVIEW_REMINDER_QUESTION);
        if (wantReminder && candidate?.id) {
            setReminderCandidate(candidate);
            return;
        }
        onSuccess();
        onClose();
    };

    const handleBook = async () => {
        try {
            setLoading(true);
            const candidateIdNum = Number(selectedCandidateId);
            await bookSlot(slot.id, candidateIdNum);
            showAlert("Слот успешно забронирован!", "success");
            const bookedCandidate = {
                ...(candidates.find((c) => String(c.id) === String(candidateIdNum)) || { id: candidateIdNum }),
            };
            try {
                const fresh = await getCandidate(candidateIdNum);
                if (fresh && typeof fresh === "object") {
                    Object.assign(bookedCandidate, fresh);
                }
            } catch (_) {
                /* keep list row */
            }
            const wantHhMessage = window.confirm(
                "Отправить кандидату сообщение о собеседовании на hh.ru?"
            );
            if (wantHhMessage) {
                setInviteCandidate(bookedCandidate);
                return;
            }
            askHrReminder(bookedCandidate);
        } catch (e) {
            showAlert(`Ошибка бронирования: ${e.message}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const afterInviteFlow = () => {
        const source = inviteCandidate
            || candidates.find((c) => String(c.id) === String(selectedCandidateId))
            || { id: Number(selectedCandidateId) };
        setInviteCandidate(null);
        askHrReminder(source);
    };

    const submitInterviewInvite = async (message, _schedule, reminder) => {
        const candidateIdNum = Number(inviteCandidate?.id || selectedCandidateId);
        try {
            const resp = await sendInterviewInvite(candidateIdNum, {
                message,
                hr_id: user?.erp_user_id || user?.id || null,
                interview_date: slot.date,
                start_time: String(slot.start_time || "").slice(0, 5),
                end_time: String(slot.end_time || "").slice(0, 5),
                book_calendar: false,
                remind_candidate: Boolean(reminder?.enabled),
                remind_at: reminder?.remind_at || null,
                reminder_message: reminder?.message || null,
            });
            if (resp?.delivery && resp.delivery !== "sent" && resp.delivery !== "ok") {
                showAlert(
                    resp?.warning || "Собеседование сохранено, но HH пока не принял приглашение.",
                    "warning"
                );
            } else {
                showAlert("Приглашение на собеседование отправлено кандидату в HH", "success");
            }
            afterInviteFlow();
        } catch (e) {
            showAlert(`Ошибка отправки приглашения: ${e?.message || e}`, "error");
            throw e;
        }
    };

    const closeAfterReminder = (refresh) => {
        setReminderCandidate(null);
        if (refresh) onSuccess();
        onClose();
    };

    return (
        <>
            {!reminderCandidate ? (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                        <h3 className="text-xl font-bold mb-4">Забронировать слот</h3>
                        <p className="text-gray-600 mb-2">
                            Дата: <span className="font-medium">{formatDateRu(slot.date)}</span>
                        </p>
                        <p className="text-gray-600 mb-4">
                            Время: <span className="font-medium">{slot.start_time} - {slot.end_time}</span>
                        </p>

                        <div className="mb-4">
                            <label className="block font-medium mb-2">Поиск кандидата</label>
                            <input
                                className="w-full border rounded p-2 mb-2"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="ФИО…"
                                data-testid="booking-candidate-search"
                            />
                            <label className="block font-medium mb-2">Выберите кандидата *</label>
                            {loadingCandidates ? (
                                <p className="text-gray-500">Загрузка...</p>
                            ) : (
                                <select
                                    value={selectedCandidateId}
                                    onChange={e => setSelectedCandidateId(e.target.value)}
                                    className="w-full border rounded p-2"
                                    data-testid="booking-candidate-select"
                                >
                                    <option value="">-- Выберите кандидата --</option>
                                    {candidates.map(c => (
                                        <option key={c.id} value={c.id}>{c.full_name || `Кандидат #${c.id}`}</option>
                                    ))}
                                </select>
                            )}
                        </div>

                        <div className="flex gap-3 justify-end flex-wrap">
                            {onDeleteSlot && (
                                <button
                                    onClick={() => onDeleteSlot(slot)}
                                    className="px-4 py-2 border border-red-300 text-red-600 rounded hover:bg-red-50 mr-auto"
                                    disabled={loading}
                                    type="button"
                                >
                                    Удалить слот
                                </button>
                            )}
                            <button
                                onClick={onClose}
                                className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                                disabled={loading}
                            >
                                Отмена
                            </button>
                            <button
                                onClick={handleBook}
                                disabled={loading || !selectedCandidateId}
                                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400"
                            >
                                {loading ? "Бронирование..." : "Забронировать"}
                            </button>
                        </div>
                    </div>
                    <InterviewInviteModal
                        open={Boolean(inviteCandidate)}
                        candidate={inviteCandidate}
                        defaultDate={slot?.date || ""}
                        defaultTime={String(slot?.start_time || "").slice(0, 5)}
                        lockSchedule
                        onClose={() => {
                            afterInviteFlow();
                        }}
                        onSubmit={submitInterviewInvite}
                    />
                </div>
            ) : null}
            <InterviewReminderModal
                open={Boolean(reminderCandidate)}
                candidate={reminderCandidate}
                date={slot.date}
                startTime={String(slot.start_time || "").slice(0, 5)}
                endTime={String(slot.end_time || "").slice(0, 5)}
                onClose={() => closeAfterReminder(false)}
                onSkip={() => closeAfterReminder(true)}
                onSaved={() => closeAfterReminder(true)}
            />
        </>
    );
}
