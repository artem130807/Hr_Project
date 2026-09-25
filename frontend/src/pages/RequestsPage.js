import { useState, useEffect } from "react";
import MainLayout from "../layout/MainLayout";
import { useAuth } from "../context/AuthContext";
import RequestFormModal from "../components/requests/RequestFormModal";
import RequestViewModal from "../components/requests/RequestViewModal";
import {
    getHiringRequests,
    createHiringRequest,
    updateHiringRequest,
    updateHiringRequestStatus,
    getHiringRequestHistory,
    createVacancyFromHiringRequest,
    publishHiringRequestToHH,
    HIRING_REQUEST_STATUS,
    canCreateHiringRequest,
    canGenerateHiringRequestInvite,
    createHiringRequestInvite,
} from "../services/hiringRequestsApi";
import { DEPARTMENTS } from "../config/api";
import VacancyFilterStepModal from "../components/vacancies/VacancyFilterStepModal";
import { formatDateRu } from "../utils/dateFormat";

const getStatusColor = (status) => {
    switch (status) {
        case "создана":
            return "bg-blue-100 text-blue-800";
        case "на анализе":
            return "bg-yellow-100 text-yellow-800";
        case "утверждена":
            return "bg-indigo-100 text-indigo-800";
        case "опубликована":
            return "bg-emerald-100 text-emerald-800";
        case "возвращена на уточнение":
            return "bg-amber-100 text-amber-800";
        case "отменена":
            return "bg-red-100 text-red-800";
        case "закрыта":
        case "завершена":
            return "bg-green-100 text-green-800";
        default:
            return "bg-gray-100 text-gray-800";
    }
};

const deadlineRowClass = (state) => {
    if (state === "overdue") return "bg-red-50 border border-red-200";
    if (state === "warning") return "bg-yellow-50 border border-yellow-200";
    return "bg-white border border-slate-200/60";
};

// Форматирование зарплаты
const formatSalary = (from, to) => {
    if (!from && !to) return "—";
    if (from && to) return `${from.toLocaleString()} - ${to.toLocaleString()}`;
    if (from) return `от ${from.toLocaleString()}`;
    return `до ${to.toLocaleString()}`;
};

export default function RequestsPage() {
    const { user } = useAuth();
    const [requests, setRequests] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Модальные окна
    const [showFormModal, setShowFormModal] = useState(false);
    const [editingRequest, setEditingRequest] = useState(null);
    const [showViewModal, setShowViewModal] = useState(false);
    const [selectedRequest, setSelectedRequest] = useState(null);

    // Состояния загрузки для операций
    const [isCreating, setIsCreating] = useState(false);
    const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
    const [isCreatingVacancy, setIsCreatingVacancy] = useState(false);
    const [isPublishingHH, setIsPublishingHH] = useState(false);
    const [filterStepVacancy, setFilterStepVacancy] = useState(null);
    const [inviteLink, setInviteLink] = useState(null);
    const [isGeneratingInvite, setIsGeneratingInvite] = useState(false);

    // Фильтры
    const [statusFilter, setStatusFilter] = useState("");
    const [departmentFilter, setDepartmentFilter] = useState("");

    // Загрузка списка заявок
    const loadRequests = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await getHiringRequests(statusFilter || null, departmentFilter || null);
            setRequests(data || []);
        } catch (err) {
            setError(err.message || "Не удалось загрузить заявки");
            console.error("Error loading requests:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [statusFilter, departmentFilter]);

    // Создание заявки
    const handleCreateRequest = async (formData) => {
        try {
            setIsCreating(true);
            const newRequest = await createHiringRequest(formData);
            setRequests(prev => [newRequest, ...prev]);
            setShowFormModal(false);
        } catch (err) {
            alert(`Ошибка создания заявки: ${err.message}`);
            console.error("Error creating request:", err);
        } finally {
            setIsCreating(false);
        }
    };

    // Обновление статуса
    const handleStatusChange = async (requestId, newStatus, details = {}) => {
        try {
            setIsUpdatingStatus(true);
            const updated = await updateHiringRequestStatus(requestId, newStatus, details);
            setRequests(prev => prev.map(r => r.id === requestId ? updated : r));
            if (selectedRequest?.id === requestId) {
                setSelectedRequest(updated);
            }
        } catch (err) {
            alert(`Ошибка обновления статуса: ${err.message}`);
            console.error("Error updating status:", err);
        } finally {
            setIsUpdatingStatus(false);
        }
    };

    // Просмотр заявки
    const handleViewRequest = async (request) => {
        setSelectedRequest(request);
        setShowViewModal(true);
        try {
            const history = await getHiringRequestHistory(request.id);
            setSelectedRequest(prev => prev?.id === request.id ? { ...prev, history: history || [] } : prev);
        } catch (_) {
            setSelectedRequest(prev => prev?.id === request.id ? { ...prev, history: [] } : prev);
        }
    };

    const handleEditRequest = async (formData) => {
        if (!editingRequest?.id) return;
        try {
            setIsCreating(true);
            const updated = await updateHiringRequest(editingRequest.id, formData);
            setRequests(prev => prev.map(item => item.id === updated.id ? updated : item));
            setEditingRequest(null);
            setShowFormModal(false);
        } catch (err) {
            alert(`Ошибка сохранения заявки: ${err.message}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleCreateVacancy = async (requestId) => {
        try {
            setIsCreatingVacancy(true);
            const vacancy = await createVacancyFromHiringRequest(requestId);
            await loadRequests();
            setSelectedRequest((prev) =>
                prev?.id === requestId
                    ? { ...prev, linked_vacancy_id: vacancy.id, status: prev.status === "создана" || prev.status === "на анализе" ? "утверждена" : prev.status }
                    : prev
            );
            alert(
                `Вакансия #${vacancy.id} создана. Откройте её в «Вакансии», укажите роль и город, затем публикуйте на HH.`
            );
            if (vacancy?.id) {
                setFilterStepVacancy(vacancy);
            }
        } catch (err) {
            alert(`Не удалось создать вакансию: ${err.message}`);
        } finally {
            setIsCreatingVacancy(false);
        }
    };

    const handlePublishHH = async (requestId) => {
        try {
            setIsPublishingHH(true);
            const result = await publishHiringRequestToHH(requestId);
            await loadRequests();
            if (result?.hiring_request) {
                setSelectedRequest(result.hiring_request);
            }
            alert(
                result?.hh_vacancy_url
                    ? `Опубликовано на HH: ${result.hh_vacancy_url}`
                    : "Заявка опубликована на HH.ru"
            );
        } catch (err) {
            alert(`Публикация на HH не удалась: ${err.message}`);
        } finally {
            setIsPublishingHH(false);
        }
    };

    const handleGenerateInvite = async () => {
        try {
            setIsGeneratingInvite(true);
            setError(null);
            const result = await createHiringRequestInvite();
            setInviteLink(result);
            try { await navigator.clipboard.writeText(result.url); } catch { /* manual copy remains available */ }
        } catch (err) {
            setError(err.message || "Не удалось создать ссылку");
        } finally {
            setIsGeneratingInvite(false);
        }
    };

    const copyInvite = async () => {
        if (!inviteLink?.url) return;
        try {
            await navigator.clipboard.writeText(inviteLink.url);
        } catch {
            window.prompt("Скопируйте ссылку", inviteLink.url);
        }
    };

    return (
        <MainLayout>
            <div className="mb-6 space-y-6">
                <div className="flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Заявки на подбор</h1>
                        <p className="mt-1 text-sm text-slate-500">Управление запросами на найм от руководителей.</p>
                    </div>

                    <div className="flex items-center gap-3">
                        {canGenerateHiringRequestInvite(user?.role) && (
                            <button
                                type="button"
                                onClick={handleGenerateInvite}
                                disabled={isGeneratingInvite}
                                className="bg-white border border-slate-200 text-slate-700 px-4 py-2.5 rounded-xl hover:bg-slate-50 transition-colors shadow-sm text-sm font-medium disabled:opacity-50"
                            >
                                {isGeneratingInvite ? "Создаём ссылку…" : "Ссылка для руководителя"}
                            </button>
                        )}
                        <button
                            onClick={loadRequests}
                            disabled={loading}
                            className="bg-white border border-slate-200 text-slate-600 p-2.5 rounded-xl hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
                            title="Обновить"
                        >
                            <svg className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                        </button>
                        
                        {canCreateHiringRequest(user?.role) && (
                            <button
                                onClick={() => setShowFormModal(true)}
                                className="bg-slate-900 text-white px-4 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
                                data-testid="create-hiring-request"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                                Создать заявку
                            </button>
                        )}
                    </div>
                </div>

                {inviteLink ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                        <div className="flex flex-col gap-3 md:flex-row md:items-center">
                            <div className="min-w-0 flex-1">
                                <p className="text-sm font-semibold text-slate-900">Ссылка для создания заявки</p>
                                <p className="mt-1 text-xs text-slate-600">Одноразовая ссылка действует до {new Date(inviteLink.expires_at).toLocaleString("ru-RU")}.</p>
                                <input readOnly value={inviteLink.url} onFocus={(event) => event.target.select()} className="mt-2 w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm text-slate-700" />
                            </div>
                            <div className="flex gap-2">
                                <button type="button" onClick={copyInvite} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white">Копировать</button>
                                <button type="button" onClick={() => setInviteLink(null)} className="rounded-xl px-3 py-2 text-sm text-slate-600 hover:bg-white">Закрыть</button>
                            </div>
                        </div>
                    </div>
                ) : null}

                <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200/60 flex flex-wrap gap-4">
                    <div className="w-full sm:w-48 relative">
                        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Статус</label>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all appearance-none cursor-pointer"
                        >
                            <option value="">Все статусы</option>
                            {Object.entries(HIRING_REQUEST_STATUS).map(([key, label]) => (
                                <option key={key} value={key}>{label}</option>
                            ))}
                        </select>
                        <div className="absolute bottom-2.5 right-3 pointer-events-none text-slate-400">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                        </div>
                    </div>

                    {(user?.role === "hr" || user?.role === "owner" || user?.role === "dev") && (
                        <div className="w-full sm:w-48 relative">
                            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Отдел</label>
                            <select
                                value={departmentFilter}
                                onChange={(e) => setDepartmentFilter(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 focus:border-[#4f46e5] transition-all appearance-none cursor-pointer"
                            >
                                <option value="">Все отделы</option>
                                {DEPARTMENTS.map((dept) => (
                                    <option key={dept} value={dept}>{dept}</option>
                                ))}
                            </select>
                            <div className="absolute bottom-2.5 right-3 pointer-events-none text-slate-400">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div>{error}</div>
                    <button
                        type="button"
                        onClick={loadRequests}
                        className="shrink-0 px-4 py-2 bg-white border border-red-200 text-red-700 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
                    >
                        Повторить
                    </button>
                </div>
            )}

            {loading && requests.length === 0 ? (
                <div className="flex justify-center items-center py-20 text-slate-400">
                    <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Загрузка заявок...
                </div>
            ) : requests.length === 0 ? (
                <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" /></svg>
                    </div>
                    <h3 className="text-lg font-medium text-slate-800">Заявок не найдено</h3>
                    <p className="text-slate-500 mt-1">
                        {statusFilter
                            ? "Нет заявок с выбранным статусом."
                            : "Пока нет ни одной заявки."}
                    </p>
                    {canCreateHiringRequest(user?.role) && !statusFilter && (
                        <button
                            type="button"
                            onClick={() => setShowFormModal(true)}
                            className="mt-4 bg-slate-900 text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-slate-800"
                        >
                            Создать первую заявку
                        </button>
                    )}
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {requests.map((request) => (
                        <div
                            key={request.id}
                            onClick={() => handleViewRequest(request)}
                            className={`rounded-2xl shadow-sm hover:shadow-md transition-shadow cursor-pointer p-6 flex flex-col justify-between ${deadlineRowClass(request.deadline_state)}`}
                        >
                            <div className="mb-4">
                                <div className="flex justify-between items-start gap-4 mb-2">
                                    <div className="flex-1">
                                        <div className="text-[10px] font-bold tracking-wider text-slate-400 uppercase mb-1">
                                            {request.public_code || `З-${request.id}`}
                                        </div>
                                        <h3 className="font-bold text-lg text-slate-900 leading-tight">{request.position}</h3>
                                    </div>
                                    <span className={`shrink-0 px-2 py-1 text-[10px] font-bold uppercase tracking-wider rounded ${getStatusColor(request.status)} border border-current/10`}>
                                        {HIRING_REQUEST_STATUS[request.status] || request.status}
                                    </span>
                                </div>
                                <p className="text-sm font-medium text-slate-500">{request.department}</p>
                            </div>

                            <div className="space-y-2.5 text-sm text-slate-600 mb-6">
                                <div className="flex items-center justify-between bg-slate-50/50 p-2 rounded-lg border border-slate-100">
                                    <span className="text-slate-400 font-medium">Кандидатов нужно:</span>
                                    <span className="text-slate-900 font-bold">{request.headcount} чел.</span>
                                </div>
                                {request.slot_summary && (
                                    <div className="grid grid-cols-2 gap-1 rounded-lg border border-slate-100 bg-white p-2 text-xs">
                                        <span className="text-slate-500">Свободно: <b className="text-slate-900">{request.slot_summary.free || 0}</b></span>
                                        <span className="text-slate-500">Запланировано: <b className="text-blue-700">{request.slot_summary.planned || 0}</b></span>
                                        <span className="text-slate-500">На адаптации: <b className="text-amber-700">{request.slot_summary.adapting || 0}</b></span>
                                        <span className="text-slate-500">Закрыто: <b className="text-emerald-700">{request.slot_summary.closed || 0}</b></span>
                                    </div>
                                )}
                                <div className="flex justify-between items-center px-1">
                                    <span className="text-slate-400">Зарплата:</span>
                                    <span className="text-slate-900 font-medium">{formatSalary(request.salary_from, request.salary_to)}</span>
                                </div>
                                {request.background_search ? (
                                    <div className="flex justify-between items-center px-1">
                                        <span className="text-slate-400">Режим:</span>
                                        <span className="text-indigo-700 font-medium">Фоновый подбор</span>
                                    </div>
                                ) : null}
                                <div className="flex justify-between items-center px-1">
                                    <span className="text-slate-400">Дней в статусе:</span>
                                    <span className="text-slate-900 font-medium">{request.days_in_status ?? "—"}</span>
                                </div>
                                {request.planned_close_date && (
                                    <div className="flex justify-between items-center px-1">
                                        <span className="text-slate-400">Дедлайн:</span>
                                        <span className={`font-medium ${
                                            request.deadline_state === "overdue" ? "text-red-600" :
                                            request.deadline_state === "warning" ? "text-yellow-600" :
                                            "text-slate-900"
                                        }`}>
                                            {formatDateRu(request.planned_close_date)}
                                        </span>
                                    </div>
                                )}
                                {(request.initiator_name || request.manager_name) && (
                                    <div className="flex justify-between items-center px-1">
                                        <span className="text-slate-400">Инициатор:</span>
                                        <span className="text-slate-900 font-medium truncate max-w-[150px]">{request.initiator_name || request.manager_name}</span>
                                    </div>
                                )}
                            </div>

                            <div className="pt-4 border-t border-slate-100 flex justify-end items-center">
                                <span className="text-sm font-medium text-[#4f46e5] flex items-center gap-1 group-hover:text-[#4338ca] transition-colors">
                                    Подробнее
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Модалка создания */}
            {showFormModal && (
                <RequestFormModal
                    onClose={() => { setShowFormModal(false); setEditingRequest(null); }}
                    onSubmit={editingRequest ? handleEditRequest : handleCreateRequest}
                    isLoading={isCreating}
                    initialData={editingRequest}
                />
            )}

            {/* Модалка просмотра */}
            {showViewModal && (
                <RequestViewModal
                    request={selectedRequest}
                    onClose={() => {
                        setShowViewModal(false);
                        setSelectedRequest(null);
                    }}
                    onStatusChange={handleStatusChange}
                    onEdit={(request) => { setEditingRequest(request); setShowViewModal(false); setShowFormModal(true); }}
                    onCreateVacancy={handleCreateVacancy}
                    onPublishHH={handlePublishHH}
                    isUpdating={isUpdatingStatus}
                    isCreatingVacancy={isCreatingVacancy}
                    isPublishingHH={isPublishingHH}
                />
            )}

            {filterStepVacancy?.id && (
                <VacancyFilterStepModal
                    vacancy={filterStepVacancy}
                    onDone={() => setFilterStepVacancy(null)}
                    onSkip={() => setFilterStepVacancy(null)}
                />
            )}
        </MainLayout>
    );
}
