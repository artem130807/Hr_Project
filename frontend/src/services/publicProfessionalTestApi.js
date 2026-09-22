import { http } from "../utils/http";

export const listPublicProfessionalResults = ({ test_id, q, position } = {}) => {
    const params = new URLSearchParams();
    if (test_id != null && test_id !== "") params.set("test_id", String(test_id));
    if (q) params.set("q", q);
    if (position) params.set("position", position);
    const qs = params.toString();
    return http.get(`/public-test-results${qs ? `?${qs}` : ""}`);
};

export const getPublicProfessionalResult = (id) =>
    http.get(`/public-test-results/${encodeURIComponent(id)}`);

/** Public (no JWT) — take page */
export const getPublicProfessionalTest = (testId) =>
    http.get(`/public/tests/${encodeURIComponent(testId)}`, { auth: false });

export const submitPublicProfessionalResult = (payload) =>
    http.post("/public/tests/results", payload, { auth: false });
