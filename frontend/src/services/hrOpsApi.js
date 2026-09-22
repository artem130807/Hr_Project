import { http } from "../utils/http";

export const getHiredEmployees = (department = null) => {
    const qs = department ? `?department=${encodeURIComponent(department)}` : "";
    return http.get(`/employees${qs}`);
};

export const getVnrHires = ({ hrUserId = null, activeOnly = true, mine = false } = {}) => {
    const params = new URLSearchParams();
    if (hrUserId) params.set("hr_user_id", String(hrUserId));
    if (activeOnly === false) params.set("active_only", "false");
    if (mine) params.set("mine", "true");
    const qs = params.toString();
    return http.get(`/vnr-hires${qs ? `?${qs}` : ""}`);
};

export const getEmployee = (id) => http.get(`/employees/${id}`);

export const createEmployee = (data) => http.post("/employees", data);

export const updateEmployee = (id, data) => http.patch(`/employees/${id}`, data);

export const deleteEmployee = (id) => http.del(`/employees/${id}`);

export const getEmployeeContacts = (id) => http.get(`/employees/${id}/contacts`);
export const createEmployeeContact = (id, data) => http.post(`/employees/${id}/contacts`, data);
export const updateContact = (id, data) => http.patch(`/contacts/${id}`, data);
export const deactivateContact = (id) => http.del(`/contacts/${id}`);
export const getOrganizationDepartments = () => http.get("/organization/departments");
export const getOrganizationDepartment = (id) => http.get(`/organization/departments/${id}`);
export const createDepartmentContact = (id, data) => http.post(`/organization/departments/${id}/contacts`, data);

export const getApprovals = ({ candidateId, vacancyId } = {}) => {
    const params = new URLSearchParams();
    if (candidateId) params.set("candidate_id", String(candidateId));
    if (vacancyId) params.set("vacancy_id", String(vacancyId));
    const qs = params.toString();
    return http.get(`/approvals${qs ? `?${qs}` : ""}`);
};

export const createApproval = (data) => http.post("/approvals", data);

export const getAuditLogs = ({ entityType, entityId, limit = 100 } = {}) => {
    const params = new URLSearchParams();
    if (entityType) params.set("entity_type", entityType);
    if (entityId != null) params.set("entity_id", String(entityId));
    params.set("limit", String(limit));
    return http.get(`/audit-logs?${params.toString()}`);
};

export const getCandidateStageHistory = (candidateId) =>
    http.get(`/candidate/${candidateId}/stage-history`);

export const getCandidateComments = (candidateId) =>
    http.get(`/candidate/${candidateId}/comments`);

export const createCandidateComment = (candidateId, data) =>
    http.post(`/candidate/${candidateId}/comments`, data);

export const deleteCandidateComment = (candidateId, commentId) =>
    http.del(`/candidate/${candidateId}/comments/${commentId}`);

export const getCompanyContacts = () => http.get("/company_contacts");

export const createCompanyContact = (data) => http.post("/company_contacts", data);

export const updateCompanyContact = (id, data) => http.put(`/company_contacts/${id}`, data);

export const deleteCompanyContact = (id) => http.del(`/company_contacts/${id}`);
