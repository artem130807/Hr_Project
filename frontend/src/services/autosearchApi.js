import { http } from "../utils/http";

export const getAvailableVacancies = () => {
    return http.get("/hh/autosearch/vacancies/available");
};

export const getActiveAutosearches = () => {
    return http.get("/hh/autosearch/active");
};

export const activateAutosearch = (vacancyId) => {
    return http.post(`/hh/autosearch/${vacancyId}/activate`);
};

export const deactivateAutosearch = (vacancyId) => {
    return http.post(`/hh/autosearch/${vacancyId}/deactivate`);
};

export const setAutosearchInviteLimit = (vacancyId, inviteLimit) => {
    return http.patch(
        `/hh/autosearch/${vacancyId}/invite-limit?invite_limit=${encodeURIComponent(inviteLimit)}`
    );
};
