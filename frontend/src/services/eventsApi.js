import { http } from "../utils/http";

export const getEvents = () => http.get("/events");
export const createEvent = (data) => http.post("/events", data);
export const updateEvent = (id, data) => http.patch(`/events/${id}`, data);
export const deleteEvent = (id) => http.del(`/events/${id}`);

/**
 * Быстрый поиск сотрудников по активным учётным записям ERP.
 * @param {string} q
 * @param {{ limit?: number, by?: 'name' | 'telegram' }} [options]
 */
export const searchEventEmployees = (q, options = {}) => {
    const { limit = 15, by = "name" } = options;
    const query = encodeURIComponent(String(q || "").trim());
    const mode = by === "telegram" ? "telegram" : "name";
    return http.get(`/events/employees/search?q=${query}&limit=${limit}&by=${mode}`);
};
