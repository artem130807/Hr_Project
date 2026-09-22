import { http } from "../utils/http";

export const listVacancyFilters = () => http.get("/vacancy-filters");

export const getVacancyFilter = (id) => http.get(`/vacancy-filters/${id}`);

export const createVacancyFilter = (data) => http.post("/vacancy-filters", data);

export const updateVacancyFilter = (id, data) =>
    http.patch(`/vacancy-filters/${id}`, data);

export const deleteVacancyFilter = (id) => http.del(`/vacancy-filters/${id}`);

export const assignFilterToVacancy = (vacancyId, filterId) =>
    http.put(`/vacancy/${vacancyId}/filter/${filterId}`);

export const unassignFilterFromVacancy = (vacancyId) =>
    http.del(`/vacancy/${vacancyId}/filter`);

/** Run VacancyFilter auto-reject now for one vacancy (HH unviewed responses). */
export const runVacancyFilterNow = (vacancyId) =>
    http.post(`/vacancy/${vacancyId}/run-filter`, {});

export function formatFilterRunSummary(s = {}) {
    const rejected = Number(s.rejected || 0);
    const checked = Number(s.checked || 0);
    const skipped = Number(s.skipped_viewed || 0);
    const errors = Number(s.errors || 0);
    const matched = Number(s.matched || 0);
    const detail = s.error_detail ? String(s.error_detail) : "";
    const batchSize = Number(s.batch_size || 0);
    const interval = Number(s.interval_minutes || 10);
    const considered = Number(s.considered || 0);
    let msg = `Фильтр: проверено ${checked}, подходят ${matched}, отказов «не подходит» ${rejected}`;
    if (considered) msg += `, в «Подумать» ${considered}`;
    if (skipped) msg += `, пропущено просмотренных ${skipped}`;
    if (s.batch_capped) {
        msg += `. За этот запуск не больше ${batchSize || 5} отказов, чтобы не нагружать HH; фон добирает по ${batchSize || 5} каждые ${interval} мин. Можно нажать ещё раз для следующей порции.`;
    }
    if (checked === 0 && errors === 0) {
        msg += ". В «Неразобранные» на HH сейчас нет откликов для проверки";
    } else if (checked === 0 && errors > 0) {
        msg += `. Ошибка прогона${detail ? `: ${detail}` : ""}`;
    } else if (errors > 0) {
        msg +=
            `. HH не принял отказ по ${errors} откликам` +
            (detail ? ` (${detail})` : " — нет права discard / платный API");
    }
    const level =
        errors > 0 && rejected === 0 && considered === 0
            ? "warning"
            : rejected > 0 || considered > 0
              ? "success"
              : "info";
    return { msg, level };
}
