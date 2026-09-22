/**
 * Helpers for paginated candidates list (infinite scroll / load more).
 */

export const CANDIDATES_PAGE_SIZE = 20;



/**
 * Normalize API payload from GET /candidates into a stable page shape.
 * Accepts PaginatedResponse or a bare array (legacy).
 */
export function normalizeCandidatesPage(data, { page = 0, perPage = CANDIDATES_PAGE_SIZE } = {}) {
    if (Array.isArray(data)) {
        const items = data;
        const total = items.length;
        const totalPages = total === 0 ? 0 : 1;
        return {
            items,
            total,
            page: page + 1,
            per_page: perPage,
            total_pages: totalPages,
            hasMore: false,
        };
    }

    const payload = data && typeof data === "object" ? data : {};
    const items = Array.isArray(payload.items) ? payload.items : [];
    const total = Number(payload.total);
    const totalPages = Number(payload.total_pages);
    const apiPage = Number(payload.page);
    const apiPerPage = Number(payload.per_page);

    const resolvedTotalPages = Number.isFinite(totalPages)
        ? totalPages
        : Number.isFinite(total) && Number.isFinite(apiPerPage) && apiPerPage > 0
          ? Math.ceil(total / apiPerPage)
          : items.length < perPage
            ? page + 1
            : page + 2;

    const resolvedPageIndex = Number.isFinite(apiPage) && apiPage >= 1 ? apiPage - 1 : page;
    const hasMore =
        resolvedTotalPages > 0
            ? resolvedPageIndex < resolvedTotalPages - 1
            : items.length >= perPage;

    return {
        items,
        total: Number.isFinite(total) ? total : items.length,
        page: Number.isFinite(apiPage) ? apiPage : page + 1,
        per_page: Number.isFinite(apiPerPage) ? apiPerPage : perPage,
        total_pages: resolvedTotalPages,
        hasMore,
    };
}

/** Append page items without duplicates (by id). */
export function mergeCandidatesById(prev, nextItems) {
    const prevList = Array.isArray(prev) ? prev : [];
    const incoming = Array.isArray(nextItems) ? nextItems : [];
    if (incoming.length === 0) return prevList;

    const seen = new Set(prevList.map((c) => c?.id).filter((id) => id != null));
    const merged = [...prevList];
    for (const item of incoming) {
        if (item?.id == null) {
            merged.push(item);
            continue;
        }
        if (seen.has(item.id)) continue;
        seen.add(item.id);
        merged.push(item);
    }
    return merged;
}
