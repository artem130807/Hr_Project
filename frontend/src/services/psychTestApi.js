import { http } from "../utils/http";

export const listPsychInstruments = () => http.get("/psych/instruments");

export const listPsychResults = ({ instrument_id, q, position } = {}) => {
    const params = new URLSearchParams();
    if (instrument_id) params.set("instrument_id", instrument_id);
    if (q) params.set("q", q);
    if (position) params.set("position", position);
    const qs = params.toString();
    return http.get(`/psych/results${qs ? `?${qs}` : ""}`);
};

export const getPsychResult = (id) => http.get(`/psych/results/${encodeURIComponent(id)}`);

/** Public (no JWT) — take page */
export const getPublicPsychInstrument = (instrumentId) =>
    http.get(`/public/psych/instruments/${encodeURIComponent(instrumentId)}`, { auth: false });

export const submitPublicPsychResult = (payload) =>
    http.post("/public/psych/results", payload, { auth: false });
