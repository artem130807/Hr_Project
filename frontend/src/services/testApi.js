import { http } from "../utils/http";

export const getTestResultImage = (resultId) =>
    http.getBlob(`/test/results/${resultId}/image`);

export const getTests = () =>
    http.get("/tests").catch(err => {
        if (err?.message?.includes("not found") || err?.message?.includes("404")) return [];
        throw err;
    });

export const getTest = (id) =>
        http.get(`/test/${id}`).catch(err => {
        if (err?.message?.includes("not found") || err?.message?.includes("404")) return null;
        throw err;
    });

export const createTest = (data) => http.post("/test", data);
export const updateTest = (id, data) => http.put(`/test/${id}`, data);
export const deleteTest = (id) => http.del(`/test/${id}`);

/** Append questions (legacy). Prefer replaceTestQuestions for form save. */
export const createTestQuestions = (testId, questions) =>
    http.post(`/test/${testId}/questions`, questions);

/** Replace full question list (create/edit form save). */
export const replaceTestQuestions = (testId, questions) =>
    http.put(`/test/${testId}/questions`, questions);

export const addTestsToVacancy = (vacancyId, testIds) =>
    http.post(`/vacancy/${vacancyId}/add_tests`, { test_ids: (testIds ?? []).map(Number) });

export const updateTestForVacancy = (vacancyId, testIds) =>
    http.put(`/vacancy/${vacancyId}/update_tests`, { test_ids: (testIds ?? []).map(Number) });

export const getTestForVacancy = (vacancyId) =>
    http.get(`/vacancy/${vacancyId}/tests`).catch(err => {
        if (err?.message?.includes("not found") || err?.message?.includes("404")) return [];
        throw err;
    });
