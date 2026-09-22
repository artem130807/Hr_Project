import React, {useState, useEffect, useCallback, useRef} from "react";
import {Calendar, momentLocalizer} from "react-big-calendar";
import moment from "moment";
import "moment/locale/ru"
import MainLayout from "../layout/MainLayout";
import {getHRAvailability, createAvailability, deleteAvailability} from "../services/sheduleApi";
import {useAlertContext} from "../context/AlertContext";
import {useAuth} from "../context/AuthContext";
import "react-big-calendar/lib/css/react-big-calendar.css"
import ExerciseModal from "../components/calendar/ExerciseModal";
import BookingModal from "../components/calendar/BookingModal";
import {getCandidate} from "../services/candidateApi";


moment.locale("ru");
const localizer = momentLocalizer(moment);

function slotToEvent(slot) {
    const name = slot.candidate_name;
    return {
        id: `avail-${slot.id}`,
        title: slot.is_booked
            ? (name ? name : "Занято")
            : "Доступен",
        start: new Date(`${slot.date}T${slot.start_time}`),
        end: new Date(`${slot.date}T${slot.end_time}`),
        type: slot.is_booked ? "booked" : "availability",
        resource: {
            ...slot,
            candidate: slot.candidate_id
                ? { id: slot.candidate_id, full_name: name || `Кандидат #${slot.candidate_id}` }
                : null,
        },
    };
}

export default function CalendarPage() {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(false);
    const [currentRange, setCurrentRange] = useState({
        start: moment().startOf("week").format("YYYY-MM-DD"),
        end: moment().endOf("week").format("YYYY-MM-DD"),
    });
    const [deleteModal, setDeleteModal] = useState({
        isOpen: false,
        slot: null
    });
    const [createModal, setCreateModal] = useState({
        isOpen: false,
        start: null,
        end: null,
    })
    const {showAlert} = useAlertContext()
    const {user} = useAuth()
    const userId = user?.erp_user_id || user?.id
    const [exerciseModal, setExerciseModal] = useState({
        isOpen: false,
        candidate: null,
    })
    const [bookingModal, setBookingModal] = useState({
        isOpen: false,
        slot: null,
    })
    const [creating, setCreating] = useState(false);
    const fetchSeq = useRef(0);
    const abortRef = useRef(null);

    const fetchData = useCallback(async () => {
        if(!userId) {
            showAlert("Не удалось определить ID пользователя HR. Выйдите и войдите снова.", "error")
            return
        }

        const seq = ++fetchSeq.current;
        abortRef.current?.abort();
        abortRef.current = new AbortController();
        const signal = abortRef.current.signal;

        setLoading(true);
        try {
            const availability = await getHRAvailability(
                userId,
                currentRange.start,
                currentRange.end,
                { signal }
            );
            if (seq !== fetchSeq.current || signal.aborted) return;
            setEvents((availability || []).map(slotToEvent))
        } catch (e) {
            if (e?.name === "AbortError" || signal.aborted || seq !== fetchSeq.current) return;
            console.error("Error fetching calendar", e)
            const msg = e?.message || String(e)
            showAlert(`Ошибка загрузки календаря: ${msg}`, "error")
        } finally {
            if (seq === fetchSeq.current) setLoading(false);
        }
    }, [userId, showAlert, currentRange])

    useEffect(() => {
        if (!userId) return undefined;
        const t = setTimeout(() => {
            fetchData();
        }, 80);
        return () => {
            clearTimeout(t);
            abortRef.current?.abort();
        };
    }, [fetchData, userId])

    const handleSelectSlot = async ({start, end}) => {
        setCreateModal({
            isOpen: true,
            start,
            end,
        })

    }

    const handleSelectEvent = async (event) => {
        if (event.type === "booked") {
            let candidate = event.resource.candidate
            if (candidate?.id) {
                try {
                    const full = await getCandidate(candidate.id);
                    if (full && typeof full === "object") {
                        candidate = { ...candidate, ...full };
                    }
                } catch (_) {
                    /* keep stub; ExerciseModal still loads vacancy by id */
                }
            }
            if (!candidate?.id) {
                showAlert("Кандидат не найден для этого слота", "warning")
                return
            }
            setExerciseModal({
                isOpen: true,
                candidate: candidate,
            })
        } else if (event.type === "availability") {
            setBookingModal({
                isOpen: true,
                slot: event.resource,
            })
        }
    }

    const confirmCreate = async () => {
        if (creating) return;
        try {
            if (!userId) {
                showAlert("Нет HR user id — перелогиньтесь", "error");
                return;
            }
            if (!createModal.start || !createModal.end) {
                showAlert("Не выбран интервал времени", "error");
                return;
            }
            const start = moment(createModal.start);
            const end = moment(createModal.end);
            if (!start.isValid() || !end.isValid()) {
                showAlert("Некорректная дата/время слота", "error");
                return;
            }
            if (!end.isAfter(start)) {
                showAlert("Конец интервала должен быть позже начала", "error");
                return;
            }
            if (end.diff(start, "minutes") < 60) {
                showAlert("Минимальная длина слота — 60 минут", "error");
                return;
            }
            const data = {
                hr_id: String(userId).trim(),
                date: start.format("YYYY-MM-DD"),
                start_time: start.format("HH:mm:ss"),
                end_time: end.format("HH:mm:ss"),
                slot_length_minutes: 60,
            };
            setCreating(true);
            const created = await createAvailability(data);
            setCreateModal({isOpen: false, start: null, end: null});
            const createdList = Array.isArray(created) ? created : [];
            if (createdList.length) {
                // Optimistic UI — don't depend on a follow-up GET that may flake.
                setEvents((prev) => {
                    const mapped = createdList.map(slotToEvent);
                    const ids = new Set(mapped.map((e) => e.id));
                    return [...mapped, ...prev.filter((e) => !ids.has(e.id))];
                });
            }
            showAlert(
                createdList.length
                    ? `Доступность добавлена (${createdList.length})`
                    : "Доступность добавлена",
                "success"
            );
            // Soft refresh — ignore network errors so create success is not undone.
            try {
                await fetchData();
            } catch (_) {
                /* already alerted inside fetchData or aborted */
            }
        } catch (e) {
            showAlert(`Ошибка создания слота: ${e.message}`, "error");
        } finally {
            setCreating(false);
        }
    };

    const confirmDelete = async () => {
        try {
            await deleteAvailability(deleteModal.slot.id)
            showAlert('Доступность удалена', 'success')
            setDeleteModal({isOpen: false, slot: null})
            await fetchData()
        } catch (e) {
            showAlert(`Ошибка удаления: ${e.message}`, "error")
        }
    }

    const handleNavigate = (newDate, view) => {
        const start = moment(newDate).startOf(view === "day" ? "day" : "week").format("YYYY-MM-DD")
        const end = moment(newDate).endOf(view === "day" ? "day" : "week").format("YYYY-MM-DD")
        setCurrentRange({start, end})
    }

    const eventStyleGetter = (event) => {
        let backgroundColor = "#10b981"

        if(event.type === "booked") {
            backgroundColor = "#ef4444"
        }

        const style = {
            backgroundColor,
            borderRadius: "5px",
            opacity: 0.8,
            color: "white",
            border: "none",
            display: "block",
        }
        return {style}
    }


    return (
        <MainLayout className="p-6">
            <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
                <h1 className="text-2xl font-bold">HR Календарь</h1>
                <button
                    type="button"
                    onClick={fetchData}
                    disabled={loading || !userId}
                    className="text-sm px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50"
                >
                    {loading ? "Загрузка…" : "Обновить"}
                </button>
            </div>
            <div className="bg-white p-4 rounded shadow" style={{height: "600px"}}>
                <Calendar
                    localizer={localizer}
                    events={events}
                    startAccessor="start"
                    endAccessor="end"
                    style={{height: "100%"}}
                    selectable
                    onSelectSlot={handleSelectSlot}
                    onSelectEvent ={handleSelectEvent}
                    onNavigate={handleNavigate}
                    eventPropGetter={eventStyleGetter}
                    views={['week', 'day']}
                    defaultView = "week"
                    messages={{
                        today: "Сегодня",
                        previous: "Назад",
                        next: "Вперёд",
                        week: "Неделя",
                        day: "День",
                        agenda: "Повестка",
                        date: "Дата",
                        time: "Время",
                        event: "Событие",
                        noEventsInRange: "Нет событий в этом диапазоне",
                        showMore: (total) => `Ещё ${total}`,
                    }}
                    step={60}
                    timeslots={1}
                    min={new Date(0,0,0,8,0,0)}
                    max={new Date(0,0,0,20,0,0)}
                />

                {deleteModal.isOpen && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                            <p className="text-gray-600 mb-4">Удалить доступность?</p>
                            <p className="text-gray-600 mb-2">Дата: {moment(deleteModal.slot?.date).format("DD.MM.YYYY")}
                            </p>
                            <p className="text-gray-600 mb-6">Время: {deleteModal.slot?.start_time} - {deleteModal.slot?.end_time}</p>

                            <div className='flex gap-3 justify-end'>
                                <button onClick={() => setDeleteModal({isOpen: false, slot: null})} className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-500">Отмена</button>
                                <button onClick={confirmDelete} className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">Удалить</button>
                            </div>
                        </div>
                    </div>
                )}

                {createModal.isOpen && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                            <h3 className="text-xl font-bold mb-4">Добавить доступность?</h3>
                            <p className="text-gray-600 mb-2">
                                Дата: {moment(createModal.start).format("DD.MM.YYYY")}
                            </p>
                            <p className="text-gray-600 mb-6">
                                Время: {moment(createModal.start).format("HH:mm")} - {moment(createModal.end).format("HH:mm")}
                            </p>

                            <div className="flex gap-3 justify-end">
                                <button
                                    type="button"
                                    onClick={() => setCreateModal({isOpen: false, start: null, end: null})}
                                    disabled={creating}
                                    className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
                                >
                                    Отмена
                                </button>

                                <button
                                    type="button"
                                    onClick={confirmCreate}
                                    disabled={creating}
                                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                                >
                                    {creating ? "Создание…" : "Создать"}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {exerciseModal.isOpen && exerciseModal.candidate && (
                <ExerciseModal candidate={exerciseModal.candidate} onClose={() => setExerciseModal({isOpen: false, candidate: null})}/>
            )}

            {bookingModal.isOpen && bookingModal.slot && (
                <BookingModal
                    slot={bookingModal.slot}
                    onClose={() => setBookingModal({isOpen: false, slot: null})}
                    onSuccess={fetchData}
                    onDeleteSlot={(slot) => {
                        setBookingModal({isOpen: false, slot: null})
                        setDeleteModal({isOpen: true, slot})
                    }}
                />
            )}
        </MainLayout>
    )
}
