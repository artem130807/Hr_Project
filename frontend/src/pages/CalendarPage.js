import React, {useState, useEffect, useCallback, useMemo, useRef} from "react";
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
import "./CalendarPage.css";


moment.locale("ru");
const localizer = momentLocalizer(moment);

const VIEW_LABELS = {
    week: "Неделя",
    day: "День",
};

function CalendarToolbar({label, onNavigate, onView, view}) {
    return (
        <div className="calendar-toolbar">
            <div className="calendar-toolbar__navigation">
                <button type="button" onClick={() => onNavigate("PREV")} aria-label="Предыдущий период">‹</button>
                <button type="button" className="calendar-toolbar__today" onClick={() => onNavigate("TODAY")}>Сегодня</button>
                <button type="button" onClick={() => onNavigate("NEXT")} aria-label="Следующий период">›</button>
            </div>
            <h2 className="calendar-toolbar__label">{label}</h2>
            <div className="calendar-toolbar__views" aria-label="Режим календаря">
                {Object.entries(VIEW_LABELS).map(([key, text]) => (
                    <button
                        key={key}
                        type="button"
                        className={view === key ? "is-active" : ""}
                        aria-pressed={view === key}
                        onClick={() => onView(key)}
                    >
                        {text}
                    </button>
                ))}
            </div>
        </div>
    );
}

function CalendarEvent({event}) {
    return (
        <div className="calendar-event" title={`${event.title}, ${moment(event.start).format("HH:mm")}–${moment(event.end).format("HH:mm")}`}>
            <span className="calendar-event__time">{moment(event.start).format("HH:mm")}</span>
            <span className="calendar-event__title">{event.title}</span>
        </div>
    );
}

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
    const [calendarDate, setCalendarDate] = useState(new Date());
    const [calendarView, setCalendarView] = useState("week");
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

    const updateRange = (date, view) => {
        const unit = view === "day" ? "day" : "week";
        const start = moment(date).startOf(unit).format("YYYY-MM-DD")
        const end = moment(date).endOf(unit).format("YYYY-MM-DD")
        setCurrentRange({start, end})
    };

    const handleNavigate = (newDate, view = calendarView) => {
        setCalendarDate(newDate);
        updateRange(newDate, view);
    };

    const handleView = (nextView) => {
        setCalendarView(nextView);
        updateRange(calendarDate, nextView);
    };

    const eventStyleGetter = (event) => {
        return {
            className: event.type === "booked"
                ? "hr-calendar-event hr-calendar-event--booked"
                : "hr-calendar-event hr-calendar-event--available",
        };
    }

    const summary = useMemo(() => {
        const available = events.filter((event) => event.type === "availability").length;
        const booked = events.filter((event) => event.type === "booked").length;
        const today = events.filter((event) => moment(event.start).isSame(moment(), "day")).length;
        return {available, booked, today, total: events.length};
    }, [events]);

    const periodLabel = useMemo(() => {
        const start = moment(currentRange.start);
        const end = moment(currentRange.end);
        if (start.isSame(end, "day")) return start.format("D MMMM YYYY");
        return `${start.format("D MMM")} — ${end.format("D MMM YYYY")}`;
    }, [currentRange]);


    return (
        <MainLayout>
            <div className="calendar-page pb-10">
                <section className="calendar-page__hero">
                    <div>
                        <p className="calendar-page__eyebrow">Рабочее расписание</p>
                        <h1>HR Календарь</h1>
                        <p className="calendar-page__description">
                            Выделите время в сетке, чтобы открыть доступный слот. Нажмите на событие, чтобы управлять записью.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={fetchData}
                        disabled={loading || !userId}
                        className="calendar-refresh"
                    >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M20 11a8.1 8.1 0 0 0-15.5-2M4 4v5h5M4 13a8.1 8.1 0 0 0 15.5 2M20 20v-5h-5" />
                        </svg>
                        {loading ? "Обновляем…" : "Обновить"}
                    </button>
                </section>

                <section className="calendar-summary" aria-label="Сводка календаря">
                    <div className="calendar-summary__item calendar-summary__item--period">
                        <span>Текущий период</span>
                        <strong>{periodLabel}</strong>
                    </div>
                    <div className="calendar-summary__item">
                        <span className="calendar-summary__dot calendar-summary__dot--available" aria-hidden="true" />
                        <div><span>Свободно</span><strong>{summary.available}</strong></div>
                    </div>
                    <div className="calendar-summary__item">
                        <span className="calendar-summary__dot calendar-summary__dot--booked" aria-hidden="true" />
                        <div><span>Записано</span><strong>{summary.booked}</strong></div>
                    </div>
                    <div className="calendar-summary__item">
                        <span className="calendar-summary__dot calendar-summary__dot--today" aria-hidden="true" />
                        <div><span>Сегодня</span><strong>{summary.today}</strong></div>
                    </div>
                </section>

                <div className="calendar-card">
                    <div className="calendar-card__hint">
                        <span>Рабочее время: 08:00–20:00</span>
                        <span>{summary.total ? `Всего слотов: ${summary.total}` : "В выбранном периоде пока нет слотов"}</span>
                    </div>
                    <div className="calendar-card__viewport">
                        <div className="calendar-card__canvas">
                            <Calendar
                                localizer={localizer}
                                culture="ru"
                                events={events}
                                date={calendarDate}
                                view={calendarView}
                                startAccessor="start"
                                endAccessor="end"
                                selectable
                                onSelectSlot={handleSelectSlot}
                                onSelectEvent={handleSelectEvent}
                                onNavigate={handleNavigate}
                                onView={handleView}
                                eventPropGetter={eventStyleGetter}
                                components={{toolbar: CalendarToolbar, event: CalendarEvent}}
                                views={["week", "day"]}
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
                                formats={{
                                    dayFormat: (date) => moment(date).format("dd, D MMM"),
                                    dayHeaderFormat: (date) => moment(date).format("dddd, D MMMM"),
                                    timeGutterFormat: (date) => moment(date).format("HH:mm"),
                                }}
                                step={60}
                                timeslots={1}
                                min={new Date(0,0,0,8,0,0)}
                                max={new Date(0,0,0,20,0,0)}
                                scrollToTime={new Date(0,0,0,9,0,0)}
                                longPressThreshold={180}
                            />
                        </div>
                    </div>
                    {loading && (
                        <div className="calendar-loading" role="status">
                            <span className="calendar-loading__spinner" />
                            Обновляем расписание…
                        </div>
                    )}
                </div>
            </div>

                {deleteModal.isOpen && (
                    <div className="calendar-modal-backdrop">
                        <div className="calendar-modal" role="dialog" aria-modal="true" aria-labelledby="delete-slot-title">
                            <div className="calendar-modal__icon calendar-modal__icon--danger">×</div>
                            <h3 id="delete-slot-title">Удалить доступность?</h3>
                            <p className="calendar-modal__description">Слот исчезнет из расписания и больше не будет доступен для записи.</p>
                            <div className="calendar-modal__details">
                                <div><span>Дата</span><strong>{moment(deleteModal.slot?.date).format("DD MMMM YYYY")}</strong></div>
                                <div><span>Время</span><strong>{deleteModal.slot?.start_time?.slice(0, 5)}–{deleteModal.slot?.end_time?.slice(0, 5)}</strong></div>
                            </div>

                            <div className="calendar-modal__actions">
                                <button onClick={() => setDeleteModal({isOpen: false, slot: null})} className="calendar-button calendar-button--secondary">Отмена</button>
                                <button onClick={confirmDelete} className="calendar-button calendar-button--danger">Удалить</button>
                            </div>
                        </div>
                    </div>
                )}

                {createModal.isOpen && (
                    <div className="calendar-modal-backdrop">
                        <div className="calendar-modal" role="dialog" aria-modal="true" aria-labelledby="create-slot-title">
                            <div className="calendar-modal__icon calendar-modal__icon--primary">+</div>
                            <h3 id="create-slot-title">Добавить доступность?</h3>
                            <p className="calendar-modal__description">Кандидаты смогут быть записаны на выбранный интервал.</p>
                            <div className="calendar-modal__details">
                                <div><span>Дата</span><strong>{moment(createModal.start).format("DD MMMM YYYY")}</strong></div>
                                <div><span>Время</span><strong>{moment(createModal.start).format("HH:mm")}–{moment(createModal.end).format("HH:mm")}</strong></div>
                            </div>

                            <div className="calendar-modal__actions">
                                <button
                                    type="button"
                                    onClick={() => setCreateModal({isOpen: false, start: null, end: null})}
                                    disabled={creating}
                                    className="calendar-button calendar-button--secondary"
                                >
                                    Отмена
                                </button>

                                <button
                                    type="button"
                                    onClick={confirmCreate}
                                    disabled={creating}
                                    className="calendar-button calendar-button--primary"
                                >
                                    {creating ? "Создание…" : "Создать"}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
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
