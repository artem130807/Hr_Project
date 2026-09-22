import { useCallback, useEffect, useRef, useState } from "react";
import { getCandidates } from "../services/candidateApi";
import { mapCandidateFromBackend } from "../utils/candidateMapper";
import {
    CANDIDATES_PAGE_SIZE,
    normalizeCandidatesPage,
    mergeCandidatesById,
} from "../utils/candidatesPagination";

function isAbortError(err) {
    return err?.name === "AbortError" || /abort/i.test(String(err?.message || ""));
}

/**
 * Abortable paginated candidates loader. Cancels in-flight list requests on filter change.
 */
export function useCandidatesList({
    statusFilter,
    debouncedSearch,
    roleFilter,
    vacancyIds,
    onlyPerfect,
    categoryFilter,
    onError,
}) {
    const [candidates, setCandidates] = useState([]);
    const [listLoading, setListLoading] = useState(false);
    const [loadingMore, setLoadingMore] = useState(false);
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [total, setTotal] = useState(null);

    const loadingLock = useRef(false);
    const hasMoreRef = useRef(true);
    const pageRef = useRef(0);
    const abortRef = useRef(null);
    const requestIdRef = useRef(0);
    const onErrorRef = useRef(onError);
    onErrorRef.current = onError;

    const vacancyIdsKey = Array.isArray(vacancyIds)
        ? vacancyIds.map(String).filter(Boolean).sort().join(",")
        : vacancyIds
          ? String(vacancyIds)
          : "";

    useEffect(() => {
        hasMoreRef.current = hasMore;
    }, [hasMore]);

    useEffect(() => {
        pageRef.current = page;
    }, [page]);

    const loadCandidatesPage = useCallback(
        async (pageNum, replace = false) => {
            if (loadingLock.current && !replace) return;
            loadingLock.current = true;

            if (replace) {
                abortRef.current?.abort();
                abortRef.current = new AbortController();
            }
            const signal = abortRef.current?.signal;
            const requestId = ++requestIdRef.current;
            const ids = vacancyIdsKey
                ? vacancyIdsKey.split(",").map((id) => {
                      const n = Number(id);
                      return Number.isFinite(n) ? n : id;
                  })
                : null;

            try {
                if (replace) setListLoading(true);
                else setLoadingMore(true);

                const data = await getCandidates(
                    statusFilter,
                    debouncedSearch,
                    roleFilter,
                    ids,
                    onlyPerfect ? true : undefined,
                    pageNum,
                    CANDIDATES_PAGE_SIZE,
                    categoryFilter || null,
                    { signal }
                );

                // Stale / aborted response — ignore
                if (requestId !== requestIdRef.current || signal?.aborted) return;

                const normalized = normalizeCandidatesPage(data, {
                    page: pageNum,
                    perPage: CANDIDATES_PAGE_SIZE,
                });
                const mapped = normalized.items.map((candidate) => mapCandidateFromBackend(candidate));

                setCandidates((prev) => (replace ? mapped : mergeCandidatesById(prev, mapped)));
                setHasMore(normalized.hasMore);
                setTotal(normalized.total);
                setPage(pageNum);
            } catch (e) {
                if (isAbortError(e) || signal?.aborted || requestId !== requestIdRef.current) return;
                onErrorRef.current?.(e);
                if (replace) {
                    setCandidates([]);
                    setHasMore(false);
                    setTotal(0);
                }
            } finally {
                // Only the latest in-flight request may clear loading flags
                if (requestId === requestIdRef.current) {
                    loadingLock.current = false;
                    setListLoading(false);
                    setLoadingMore(false);
                }
            }
        },
        [
            statusFilter,
            debouncedSearch,
            roleFilter,
            vacancyIdsKey,
            onlyPerfect,
            categoryFilter,
        ]
    );

    const loadNextPage = useCallback(() => {
        if (loadingLock.current || listLoading || loadingMore) return;
        if (!hasMoreRef.current) return;
        loadCandidatesPage(pageRef.current + 1, false);
    }, [listLoading, loadingMore, loadCandidatesPage]);

    const reloadFirstPage = useCallback(() => {
        setPage(0);
        setHasMore(true);
        loadCandidatesPage(0, true);
    }, [loadCandidatesPage]);

    // Debounced reload when filters change (also absorbs React StrictMode double-mount).
    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(0);
            setHasMore(true);
            loadCandidatesPage(0, true);
        }, 120);
        return () => {
            clearTimeout(timer);
            abortRef.current?.abort();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [statusFilter, debouncedSearch, roleFilter, vacancyIdsKey, onlyPerfect, categoryFilter]);

    useEffect(() => {
        return () => abortRef.current?.abort();
    }, []);

    return {
        candidates,
        setCandidates,
        listLoading,
        loadingMore,
        page,
        hasMore,
        total,
        setTotal,
        loadNextPage,
        reloadFirstPage,
        loadCandidatesPage,
    };
}
