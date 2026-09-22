import {http} from "../utils/http";

export const getHRAvailability = (hrId, dateFrom, dateTo, opts = {}) => {
    const params = new URLSearchParams({
        date_from: dateFrom,
        date_to: dateTo
    });
    const id = encodeURIComponent(String(hrId ?? "").trim());
    return http.get(`/availability/hr/${id}?${params.toString()}`, opts);
};
export const createAvailability = (data, opts = {}) =>
    http.post(
        "/availability/hr",
        {
            ...data,
            hr_id: String(data?.hr_id ?? "").trim(),
        },
        opts
    );
export const deleteAvailability = (id) => http.del(`/availability/${id}`)
export const bookSlot = (slotId, candidateId) => http.post(`/availability/book/${slotId}/${candidateId}`)
export const ensureBookSlot = (data) =>
    http.post("/availability/ensure-book", {
        hr_id: String(data?.hr_id ?? "").trim(),
        candidate_id: Number(data?.candidate_id),
        date: data?.date,
        start_time: data?.start_time,
        ...(data?.end_time ? { end_time: data.end_time } : {}),
    });
export const unbookSlot = (slotId) => http.post(`/availability/unbook/${slotId}`)
