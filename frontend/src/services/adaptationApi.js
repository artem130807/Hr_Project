import { http } from "../utils/http";

export const listAdaptationCheckpoints = (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
        if (v === undefined || v === null || v === "" || v === false) return;
        qs.set(k, String(v));
    });
    const suffix = qs.toString();
    return http.get(`/adaptation/checkpoints${suffix ? `?${suffix}` : ""}`);
};

export const getAdaptationCheckpoint = (id) => http.get(`/adaptation/checkpoints/${id}`);

export const getAdaptationEnrollment = (id) => http.get(`/adaptation/enrollments/${id}`);

export const enrollAdaptation = (data) => http.post("/adaptation/enrollments", data);

export const addAdaptationCheckpoint = (data) => http.post("/adaptation/checkpoints", data);

export const submitAdaptationAnswer = (id, data) =>
    http.post(`/adaptation/checkpoints/${id}/answers`, data);

export const rescheduleAdaptationCheckpoint = (id, data) =>
    http.post(`/adaptation/checkpoints/${id}/reschedule`, data);

export const forceCompleteAdaptationCheckpoint = (id, data) =>
    http.post(`/adaptation/checkpoints/${id}/force-complete`, data);

export const finalizeAdaptationCheckpoint = (id, data) =>
    http.post(`/adaptation/checkpoints/${id}/finalize`, data);

export const finalizeAdaptationEnrollment = (id, data) =>
    http.post(`/adaptation/enrollments/${id}/finalize`, data);

export const changeAdaptationManager = (id, data) =>
    http.post(`/adaptation/enrollments/${id}/manager`, data);

export const createTemporaryAdaptation = (data) =>
    http.post("/adaptation/temporary-employees", data);

export const linkTemporaryAdaptation = (id, data) =>
    http.post(`/adaptation/temporary-employees/${id}/link`, data);

export const getTemporaryAdaptationMatches = (id) =>
    http.get(`/adaptation/temporary-employees/${id}/matches`);

export const getAdaptationActions = (id) =>
    http.get(`/adaptation/enrollments/${id}/actions`);

export const createAdaptationAction = (id, data) =>
    http.post(`/adaptation/enrollments/${id}/actions`, data);

export const updateAdaptationAction = (id, data) =>
    http.patch(`/adaptation/actions/${id}`, data);

export const archiveAdaptationEnrollment = (id, data) =>
    http.post(`/adaptation/enrollments/${id}/archive`, data);

export const restartAdaptationEnrollment = (id, data) =>
    http.post(`/adaptation/enrollments/${id}/restart`, data);

export const generateAdaptationDocuments = (id, data) =>
    http.post(`/adaptation/checkpoints/${id}/documents`, data);

export const getAdaptationDocuments = (id) =>
    http.get(`/adaptation/enrollments/${id}/documents`);

export const downloadAdaptationDocument = (id) =>
    http.getBlob(`/adaptation/documents/${id}/download`);

export const deleteAdaptationDocument = (id) => http.del(`/adaptation/documents/${id}`);

export const downloadAdaptationDocumentsZip = (id) =>
    http.getBlob(`/adaptation/enrollments/${id}/documents.zip`);

export const getAdaptationSettings = () => http.get("/adaptation/settings");
export const updateAdaptationSettings = (data) => http.put("/adaptation/settings", data);
export const getAdaptationNotificationTemplates = () => http.get("/adaptation/notification-templates");
export const updateAdaptationNotificationTemplate = (audience, event, data) =>
    http.put(`/adaptation/notification-templates/${audience}/${event}`, data);
export const getAdaptationNotificationErrors = () => http.get("/adaptation/notification-errors");
export const retryAdaptationNotification = (id) => http.post(`/adaptation/notification-errors/${id}/retry`, {});

export const getAdaptationTakeLinks = (id, includeInternal = false) =>
    http.get(`/adaptation/enrollments/${id}/take-links${includeInternal ? "?include_internal=true" : ""}`);
export const rotateAdaptationFormToken = (formId, data) => http.post(`/adaptation/forms/${formId}/rotate-token`, data);
export const updateAdaptationRoutingPolicy = (id, data) => http.patch(`/adaptation/enrollments/${id}/routing-policy`, data);
export const resolveAdaptationRecipient = (id) => http.post(`/adaptation/enrollments/${id}/resolve-recipient`, {});
export const getAdaptationRoutingDecisions = (id) => http.get(`/adaptation/enrollments/${id}/routing-decisions`);

export const getPublicAdaptationForm = (token) =>
    http.get(`/public/adaptation/forms/${encodeURIComponent(token)}`, { auth: false });

export const submitPublicAdaptationForm = (token, payload) =>
    http.post(`/public/adaptation/forms/${encodeURIComponent(token)}`, { payload }, { auth: false });

export const getAdaptationCatalog = () => http.get("/adaptation/catalog");

export const getAdaptationReports = (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
        if (v != null && v !== "") qs.set(k, String(v));
    });
    const suffix = qs.toString();
    return http.get(`/adaptation/reports${suffix ? `?${suffix}` : ""}`);
};
