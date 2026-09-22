import {http} from "../utils/http";

export const formatDetail = (detail, fallback) => {
    if (detail == null || detail === "") return fallback;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        return detail
            .map((item) => {
                if (typeof item === "string") return item;
                if (item && typeof item === "object") {
                    return item.msg || item.message || JSON.stringify(item);
                }
                return String(item);
            })
            .filter(Boolean)
            .join("; ") || fallback;
    }
    if (typeof detail === "object") {
        return detail.msg || detail.message || JSON.stringify(detail);
    }
    return String(detail);
};

/**
 * Publish/update/delete on HH go through database-service proxy
 * (`/vacancy/{id}/hh`) so SPA uses the same host that already works for CRUD.
 */
const publishViaDbProxy = (method, vacancyId, body) => {
    const path = `/vacancy/${vacancyId}/hh`;
    if (method === "POST") return http.post(path, body ?? {});
    if (method === "PUT") return http.put(path, body ?? {});
    if (method === "DELETE") return http.del(path);
    throw new Error(`Unsupported HH proxy method: ${method}`);
};

/** Publish new vacancy to HH.ru */
export const postVacancyToHH = (vacancyId, payload = {}) =>
    publishViaDbProxy("POST", vacancyId, payload);

/** Push local edits to already published HH vacancy */
export const syncVacancyToHH = (vacancyId) =>
    publishViaDbProxy("PUT", vacancyId, {});

/** Archive+hide on HH and clear local hh_vacancy_* links */
export const removeVacancyFromHH = (vacancyId) =>
    publishViaDbProxy("DELETE", vacancyId);

export const getVacancies = (department = null, opts = {}) =>  {
    const params = department ? `?department=${encodeURIComponent(department)}` : ''
    return http.get(`/vacancies${params}`, opts);
}

const toVacancyOption = (v) => ({
    id: v?.id,
    name: v?.name || `Вакансия #${v?.id ?? "?"}`,
    hh_vacancy_id: v?.hh_vacancy_id ?? null,
    hh_vacancy_url: v?.hh_vacancy_url ?? null,
});

/**
 * Slim vacancy rows for filters/selects.
 * Tries /vacancies/options, then /vacancies/published only — never the heavy full /vacancies
 * list (large descriptions) which can starve /candidates and surface as Failed to fetch.
 */
export const getVacancyOptions = async ({ hhOnly = false, signal } = {}) => {
    const opts = signal ? { signal } : {};
    try {
        const params = new URLSearchParams();
        if (hhOnly) params.set("hh_only", "true");
        const qs = params.toString();
        const data = await http.get(`/vacancies/options${qs ? `?${qs}` : ""}`, opts);
        if (Array.isArray(data) && data.length >= 0) {
            const rows = data.map(toVacancyOption);
            // options with hh_only=false returns all; with hhOnly filter client-side if needed
            return hhOnly ? rows.filter((v) => v.hh_vacancy_id) : rows;
        }
    } catch (e) {
        if (e?.name === "AbortError") throw e;
        console.warn("getVacancyOptions: /vacancies/options failed, falling back to published", e);
    }

    // Lightweight fallback: published HH vacancies only (no full description payload).
    const published = await http.get("/vacancies/published", opts);
    return (Array.isArray(published) ? published : []).map(toVacancyOption);
};

/** Full published vacancies (heavy). Prefer getVacancyOptions({ hhOnly: true }) for filters. */
export const getPublishedVacancies = async ({ signal } = {}) => {
    const data = await http.get("/vacancies/published", signal ? { signal } : {});
    return Array.isArray(data) ? data : [];
};


export const createVacancy = (data) => http.post("/vacancy", data);

/**
 * Update vacancy locally. database-service auto-syncs to HH.ru when
 * the vacancy already has hh_vacancy_id (see PATCH /vacancy/{id}).
 * Server returns hh_synced / hh_sync_error (soft-fail); local save always succeeds.
 * `syncHH` forces an extra PUT /vacancy/{id}/hh if the server did not attempt sync.
 */
export const updateVacancy = async (id, data, { syncHH = false } = {}) => {
    const result = await http.patch(`/vacancy/${id}`, data);

    if (result?.hh_synced === true) {
        return { ...result, _hhSynced: true };
    }
    if (result?.hh_synced === false || result?.hh_sync_error) {
        return {
            ...result,
            _hhSynced: false,
            _hhSyncError: result.hh_sync_error || "HH sync failed",
        };
    }

    const shouldSync = syncHH && Boolean(result?.hh_vacancy_id);
    if (!shouldSync) {
        return { ...result, _hhSynced: false };
    }

    try {
        const synced = await syncVacancyToHH(id);
        return {
            ...result,
            hh_vacancy_id: synced?.hh_vacancy_id ?? result?.hh_vacancy_id,
            hh_vacancy_url: synced?.alternate_url ?? synced?.hh_vacancy_url ?? result?.hh_vacancy_url,
            _hhSynced: true,
        };
    } catch (err) {
        return {
            ...result,
            _hhSynced: false,
            _hhSyncError: err.message || String(err),
        };
    }
};

/**
 * Delete only the local vacancy. HH publication has an independent lifecycle
 * and is removed only through the explicit `removeVacancyFromHH` action.
 */
export const deleteVacancy = async (id) => {
    if (!id) {
        throw new Error("Vacancy ID is required");
    }

    await http.del(`/vacancy/${id}`);
    return { ok: true };
};

export const generateVacancySummary = (vacancyId) => http.post(`/vacancy/${vacancyId}/summary`)

export const generateVacancyDescriptionAndSalary = (vacancyId) =>
    http.post(`/vacancy/${vacancyId}/description-salary-combine`);

export const getVacancyDescription = async (id) => {
    const allVacancies = await http.get('/vacancies');
    const list = Array.isArray(allVacancies) ? allVacancies : (allVacancies?.items ?? []);
    const vacancy = list.find(v => v.id === parseInt(id, 10));
    return vacancy?.description || '';
};


export const mapVacancyToHH = (id) => http.get(`/vacancy/${id}/map-to-hh`);

export const makeVacancyTemplate = (id) => http.post(`/vacancy/${id}/make-template`, {});

export const getVacancyTypes = async () => {
    return http.get('/vacancy_type');
};

const normalizeRoles = (d) => {
    if (Array.isArray(d)) return d;

    const unwrap = (x) => Array.isArray(x) ? x : undefined;
    const a = unwrap(d?.items) || unwrap(d?.data) || unwrap(d?.results) || unwrap(d?.data?.items);
    if (a) return a;

    if (Array.isArray(d?.categories)) {
        const flat = d.categories.flatMap(cat => {
            const roles = cat?.roles ?? cat?.specializations ?? cat?.items ?? [];
            if (Array.isArray(roles)) return roles;
            return [];
        });
        if (flat.length) return flat;
    }

    if (Array.isArray(d?.professional_roles)) {
        const flat = d.professional_roles.flatMap(cat => {
            const roles = cat?.roles ?? cat?.specializations ?? cat?.items ?? [];
            if (Array.isArray(roles)) return roles;
            return [];
        });
        if (flat.length) return flat;
    }

    if (d && typeof d === 'object') {
        const entries = Object.entries(d).filter(([, v]) => typeof v === 'string' || (v && typeof v === 'object'));
        if (entries.length) {
            const allStrings = entries.every(([, v]) => typeof v === 'string');
            if (allStrings) {
                return entries.map(([id, name]) => ({ id: String(id), name: String(name) }));
            }
            return entries.map(([k, v]) => ({
                id: String(v?.id ?? k),
                name: String(v?.name ?? v?.title ?? v?.label ?? k)
            }));
        }
    }
    return [];
};

export const getProfessionalRoles = async (q = '') => {
    const data = await http.get('/professional_roles');
    const roles = normalizeRoles(data);
    if (!q) return roles;
    const needle = q.toLowerCase();
    return roles.filter(r => String(r?.name || '').toLowerCase().includes(needle));
};
