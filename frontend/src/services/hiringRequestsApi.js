import { http } from "../utils/http";

export const getHiringRequests = (status = null, department = null) => {
    const search = new URLSearchParams();
    if (status) search.append("status", status);
    if (department) search.append("department", department);
    const qs = search.toString();
    const suffix = qs ? `?${qs}` : "";
    return http.get(`/hiring-requests${suffix}`);
};

export const createHiringRequest = (data) => {
    return http.post("/hiring-requests", data);
};

export const createHiringRequestInvite = () => http.post("/hiring-request-invites", {});

export const getPublicHiringRequestInvite = (token) => (
    http.get(`/public/hiring-request-invites/${encodeURIComponent(token)}`, { auth: false })
);

export const submitPublicHiringRequest = (token, data) => (
    http.post(`/public/hiring-request-invites/${encodeURIComponent(token)}`, data, { auth: false })
);

export const updateHiringRequest = (requestId, data) => {
    return http.patch(`/hiring-requests/${requestId}`, data);
};

export const getHiringRequestHistory = (requestId) => http.get(`/hiring-requests/${requestId}/history`);

export const updateHiringRequestStatus = (requestId, status, details = {}) => {
    return http.put(`/hiring-requests/${requestId}/status`, { status, ...details });
};

export const createVacancyFromHiringRequest = (requestId) => {
    return http.post(`/hiring-requests/${requestId}/create-vacancy`, {});
};

export const publishHiringRequestToHH = (requestId) => {
    return http.post(`/hiring-requests/${requestId}/publish-hh`, {});
};

export const deleteHiringRequest = (requestId) => {
    return http.del(`/hiring-requests/${requestId}`);
};

export const HIRING_REQUEST_STATUS = {
    "создана": "Новая",
    "на анализе": "На анализе",
    "утверждена": "Утверждена",
    "опубликована": "Опубликована",
    "возвращена на уточнение": "Возвращена на уточнение",
    "закрыта": "Закрыта",
    "отменена": "Отменена",
    "завершена": "Завершена",
};

/** Who may open the «Создать заявку» form (legacy HR + ERP leader/admin roles). */
export const HIRING_REQUEST_CREATE_ROLES = [
    "lead",
    "owner",
    "hr",
    "dev",
    "leader",
    "dept_leader",
    "admin",
    "superadmin",
    "senior_manager",
    "manager",
];

export function canCreateHiringRequest(role) {
    return HIRING_REQUEST_CREATE_ROLES.includes(String(role || "").trim());
}

export const HIRING_REQUEST_INVITE_ROLES = [
    "hr", "owner", "dev", "admin", "superadmin", "senior_manager", "manager",
];

export function canGenerateHiringRequestInvite(role) {
    return HIRING_REQUEST_INVITE_ROLES.includes(String(role || "").trim());
}
