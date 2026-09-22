import { http } from "../utils/http";

export const getHHEmployerVacancies = ({
    archived = false,
    page = 0,
    per_page = 50,
    all_accessible = true,
    text,
} = {}) => {
    const params = new URLSearchParams({
        archived: String(archived),
        page: String(page),
        per_page: String(per_page),
        all_accessible: String(all_accessible),
    });
    if (text) params.set("text", String(text));
    return http.get(`/hh/employer-vacancies?${params.toString()}`);
};

export const getHHVacancyNegotiations = (
    hhVacancyId,
    { collection = "response", page = 0, per_page = 50 } = {}
) => {
    const params = new URLSearchParams({
        collection,
        page: String(page),
        per_page: String(per_page),
    });
    return http.get(`/hh/vacancies/${encodeURIComponent(hhVacancyId)}/negotiations?${params.toString()}`);
};

export const linkHHVacancyToLocal = (hhVacancyId, localVacancyId) => {
    const params = new URLSearchParams({ local_vacancy_id: String(localVacancyId) });
    return http.post(`/hh/vacancies/${encodeURIComponent(hhVacancyId)}/link?${params.toString()}`, {});
};

/** Create local vacancy from HH (name, salary, area, …) and set hh_vacancy_id. */
export const importHHVacancyToLocal = (hhVacancyId, department) => {
    const params = new URLSearchParams({ department: String(department) });
    return http.post(
        `/hh/vacancies/${encodeURIComponent(hhVacancyId)}/import?${params.toString()}`,
        {}
    );
};

export const importHHNegotiation = (hhVacancyId, negotiationId, { collection = "response" } = {}) => {
    const params = new URLSearchParams({ collection });
    return http.post(
        `/hh/vacancies/${encodeURIComponent(hhVacancyId)}/negotiations/${encodeURIComponent(negotiationId)}/import?${params.toString()}`,
        {}
    );
};

export const getHHNegotiationDetail = (negotiationId) => {
    return http.get(`/hh/negotiations/${encodeURIComponent(negotiationId)}`);
};

export const executeHHNegotiationAction = (negotiationId, actionId, { arguments: args } = {}) => {
    return http.post(
        `/hh/negotiations/${encodeURIComponent(negotiationId)}/actions/${encodeURIComponent(actionId)}`,
        { arguments: args || null }
    );
};
