/**
 * Build candidate vacancy filter options from local rows + HH employer list.
 * Only vacancies linked to the platform (hh_vacancy_id / local_vacancy_id) are filterable.
 */
export function mergeHhVacancyFilterOptions(localOptions = [], hhItems = []) {
    const byId = new Map();

    for (const v of localOptions || []) {
        if (v?.id == null) continue;
        if (!v.hh_vacancy_id && !v.hh_vacancy_url) continue;
        const id = Number(v.id);
        if (!Number.isFinite(id)) continue;
        byId.set(id, {
            id,
            name: v.name || `Вакансия #${id}`,
            hh_vacancy_id: v.hh_vacancy_id ?? null,
            hh_vacancy_url: v.hh_vacancy_url ?? null,
        });
    }

    let unboundHhCount = 0;
    for (const item of hhItems || []) {
        const localId = item?.local_vacancy_id;
        if (localId != null && localId !== "") {
            const id = Number(localId);
            if (!Number.isFinite(id)) continue;
            const prev = byId.get(id);
            byId.set(id, {
                id,
                name: item.name || prev?.name || `Вакансия #${id}`,
                hh_vacancy_id: item.hh_vacancy_id ?? prev?.hh_vacancy_id ?? null,
                hh_vacancy_url: item.alternate_url ?? prev?.hh_vacancy_url ?? null,
            });
        } else if (!item?.archived) {
            unboundHhCount += 1;
        }
    }

    const options = [...byId.values()].sort((a, b) =>
        String(a.name).localeCompare(String(b.name), "ru")
    );
    return { options, unboundHhCount };
}
