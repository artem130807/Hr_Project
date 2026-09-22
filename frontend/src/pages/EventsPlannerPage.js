import React, { useEffect, useState } from "react";
import { getEvents } from "../services/eventsApi";
import EventsCalendar from "../components/events/EventsCalendar";
import EventList from "../components/events/EventList";
import EventNotificationSetup from "../components/events/EventNotificationSetup";
import ExportEventsButton from "../components/events/ExportEventsButton";
import MainLayout from "../layout/MainLayout";
import { useAlertContext } from "../context/AlertContext";

const EventsPlannerPage = () => {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const { showAlert } = useAlertContext();

    const fetchEvents = async () => {
        try {
            setLoading(true);
            const data = await getEvents();
            setEvents(Array.isArray(data) ? data : []);
        } catch (e) {
            console.error(e);
            showAlert(`Ошибка загрузки событий: ${e.message}`, "error");
            setEvents([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchEvents();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <div className="mb-6 space-y-6">
                <div className="flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">HR-планировщик</h1>
                        <p className="mt-1 text-sm text-slate-500">Управление событиями, собеседованиями и уведомлениями.</p>
                    </div>
                </div>
                
                {loading ? (
                    <div className="flex justify-center items-center py-20 text-slate-400">
                        <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Загрузка событий...
                    </div>
                ) : (
                    <div className="space-y-6">
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 p-6 flex flex-col xl:flex-row gap-6 items-start xl:items-end justify-between">
                            <EventNotificationSetup onRefresh={fetchEvents} />
                            <div className="hidden xl:block w-px h-12 bg-slate-200"></div>
                            <ExportEventsButton events={events} />
                        </div>
                        
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 p-6">
                            <h3 className="text-lg font-bold text-slate-900 mb-6">Календарь событий</h3>
                            <EventsCalendar events={events} />
                        </div>
                        
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 p-6">
                            <h3 className="text-lg font-bold text-slate-900 mb-6">Список предстоящих событий</h3>
                            <EventList events={events} onRefresh={fetchEvents} />
                        </div>
                    </div>
                )}
            </div>
        </MainLayout>
    );
};

export default EventsPlannerPage;
