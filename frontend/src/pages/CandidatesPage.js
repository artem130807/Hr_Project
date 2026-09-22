import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { deleteCandidate, getCandidatesStatuses } from "../services/candidateApi";
import { getVacancyOptions } from "../services/vacancyApi";
import { getHHEmployerVacancies } from "../services/hhImportApi";
import { mergeHhVacancyFilterOptions } from "../utils/hhVacancyFilterOptions";
import CandidateList from "../components/candidates/CandidateList";
import CandidatesFilters from "../components/candidates/CandidatesFilters";
import { useAlertContext } from "../context/AlertContext";
import MainLayout from "../layout/MainLayout";
import CandidateForm from "../components/candidates/CandidateForm";
import CandidateDetails from "../components/candidates/CandidateDetails";
import { useCandidatesList } from "../hooks/useCandidatesList";

export default function CandidatesPage() {
  const [shownForm, setShownForm] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [editingCandidate, setEditingCandidate] = useState(null);
  const [statusFilter, setStatusFilter] = useState(null);
  /** Default: active hiring funnel — «актуальные» кандидаты */
  const [categoryFilter, setCategoryFilter] = useState("candidate");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { showAlert } = useAlertContext();
  const [statusDict, setStatusDict] = useState([]);
  const [roleFilter] = useState("");
  const [vacancyOptions, setVacancyOptions] = useState([]);
  const [allVacancyOptions, setAllVacancyOptions] = useState([]);
  const [unboundHhCount, setUnboundHhCount] = useState(0);
  const [vacanciesLoading, setVacanciesLoading] = useState(true);
  const [selectedVacancyIds, setSelectedVacancyIds] = useState([]);
  const [onlyPerfect, setOnlyPerfect] = useState(false);
  const observer = useRef(null);

  const vacancyIdsKey = useMemo(
    () => selectedVacancyIds.map(String).sort().join(","),
    [selectedVacancyIds]
  );
  const vacancyIds = useMemo(
    () => (vacancyIdsKey ? vacancyIdsKey.split(",").map((id) => Number(id) || id) : []),
    [vacancyIdsKey]
  );

  const onListError = useCallback(
    (e) => {
      console.error("Ошибка загрузки кандидатов:", e);
      showAlert("Ошибка загрузки кандидатов: " + (e.message || "Unknown error"), "error");
    },
    [showAlert]
  );

  const {
    candidates,
    setCandidates,
    listLoading,
    loadingMore,
    hasMore,
    total,
    setTotal,
    loadNextPage,
    reloadFirstPage,
  } = useCandidatesList({
    statusFilter,
    debouncedSearch,
    roleFilter,
    vacancyIds,
    onlyPerfect,
    categoryFilter,
    onError: onListError,
  });

  const isArchiveStatus = (s) => {
    const v = typeof s === "object" ? (s?.code ?? s?.name ?? s?.id) : s;
    const val = String(v ?? "").trim();
    return ["отказ", "не подходит", "отказался", "уволился"].includes(val);
  };

  useEffect(() => {
    (async () => {
      try {
        const list = await getCandidatesStatuses();
        setStatusDict(list);
      } catch (e) {
        console.error("Не удалось загрузить статусы кандидата", e);
        setStatusDict([]);
      }
    })();
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      setVacanciesLoading(true);
      try {
        // Local cards + HH employer list (linked only). HH tab can show unbound
        // vacancies that are not yet filterable until import/link.
        const [localList, hhData] = await Promise.all([
          getVacancyOptions({ hhOnly: false, signal: ac.signal }),
          getHHEmployerVacancies({
            archived: false,
            page: 0,
            per_page: 100,
            all_accessible: true,
          }).catch((e) => {
            if (e?.name === "AbortError") throw e;
            console.warn("HH employer vacancies for candidates filter failed", e);
            return { items: [] };
          }),
        ]);
        if (ac.signal.aborted) return;
        const local = Array.isArray(localList) ? localList : [];
        setAllVacancyOptions(local);
        const { options, unboundHhCount: unbound } = mergeHhVacancyFilterOptions(
          local,
          hhData?.items || []
        );
        setVacancyOptions(options);
        setUnboundHhCount(unbound);
      } catch (e) {
        if (e?.name === "AbortError") return;
        console.error("Не удалось загрузить вакансии", e);
        if (!ac.signal.aborted) {
          setVacancyOptions([]);
          setAllVacancyOptions([]);
          setUnboundHhCount(0);
          showAlert(
            "Фильтр вакансий временно недоступен: " + (e.message || e),
            "warning"
          );
        }
      } finally {
        if (!ac.signal.aborted) setVacanciesLoading(false);
      }
    })();
    return () => ac.abort();
  }, [showAlert]);

  const handleStatusFilterChange = (e) => {
    const v = e.target.value;
    if (!v) {
      setStatusFilter(null);
    } else {
      const found = statusDict.find((s) => String(s.code) === v || String(s.id) === v);
      setStatusFilter(found ?? v);
    }
  };

  const toggleVacancy = (id) => {
    const key = String(id);
    setSelectedVacancyIds((prev) => {
      const set = new Set(prev.map(String));
      if (set.has(key)) set.delete(key);
      else set.add(key);
      return Array.from(set);
    });
  };

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Infinite scroll sentinel
  const lastCandidateRef = useCallback(
    (node) => {
      if (observer.current) observer.current.disconnect();
      if (!node) return;

      observer.current = new IntersectionObserver(
        (entries) => {
          if (entries[0]?.isIntersecting) {
            loadNextPage();
          }
        },
        { root: null, rootMargin: "240px 0px", threshold: 0 }
      );
      observer.current.observe(node);
    },
    [loadNextPage]
  );

  useEffect(() => {
    return () => {
      if (observer.current) observer.current.disconnect();
    };
  }, []);

  const handleAddCandidate = () => {
    setEditingCandidate(null);
    setShownForm(true);
  };

  const handleCandidateEdit = (candidate) => {
    setEditingCandidate(candidate);
    setShownForm(true);
  };

  const handleCandidateDeleted = async (id) => {
    if (!id) return;
    if (!window.confirm("Удалить кандидата?")) return;
    try {
      await deleteCandidate(id);
      showAlert("Кандидат удалён", "success");
      setCandidates((prev) => prev.filter((c) => c.id !== id));
      if (selectedCandidate?.id === id) setSelectedCandidate(null);
      setTotal((t) => (typeof t === "number" ? Math.max(0, t - 1) : t));
    } catch (e) {
      console.error("Ошибка при удалении", e);
      showAlert(`Ошибка при удалении: ${e.message || "Unknown error"}`, "error");
    }
  };

  const handleFormSuccess = (saved) => {
    if (saved?.id) {
      setCandidates((prev) => {
        const exists = prev.some((c) => c.id === saved.id);
        return exists ? prev.map((c) => (c.id === saved.id ? saved : c)) : [saved, ...prev];
      });
    }
    reloadFirstPage();
    setShownForm(false);
    setEditingCandidate(null);
  };

  const handleCloseForm = () => {
    setShownForm(false);
    setEditingCandidate(null);
  };

  return (
    <MainLayout className="flex flex-col h-full overflow-y-auto">
      <div className="mb-6 space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">База кандидатов</h1>
            <p className="mt-1 text-sm text-slate-500">
              Актуальные кандидаты в воронке найма. Фильтр по опубликованным вакансиям HH.ru.
              {typeof total === "number" ? (
                <span className="ml-1 text-slate-400">· найдено: {total}</span>
              ) : null}
            </p>
          </div>
          <button
            onClick={handleAddCandidate}
            className="bg-slate-900 text-white px-4 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Добавить кандидата
          </button>
        </div>

        <CandidatesFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          statusFilter={statusFilter}
          statusDict={statusDict}
          onStatusChange={handleStatusFilterChange}
          vacancyOptions={vacancyOptions}
          selectedVacancyIds={selectedVacancyIds}
          onToggleVacancy={toggleVacancy}
          onClearVacancies={() => setSelectedVacancyIds([])}
          vacanciesLoading={vacanciesLoading}
          unboundHhCount={unboundHhCount}
          categoryFilter={categoryFilter}
          onCategoryChange={setCategoryFilter}
          onlyPerfect={onlyPerfect}
          onOnlyPerfectChange={setOnlyPerfect}
        />
      </div>

      {listLoading && candidates.length === 0 ? (
        <div className="flex justify-center items-center py-20 text-slate-400">
          <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          Загружаем кандидатов...
        </div>
      ) : candidates.length === 0 && !listLoading ? (
        <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-slate-800">Кандидаты не найдены</h3>
          <p className="text-slate-500 mt-1">
            Попробуйте изменить параметры поиска или добавить нового.
          </p>
        </div>
      ) : (
        <>
          <CandidateList
            candidates={candidates}
            vacancies={allVacancyOptions.length ? allVacancyOptions : vacancyOptions}
            onCandidateDelete={handleCandidateDeleted}
            onCandidateEdit={handleCandidateEdit}
            onCandidateClick={setSelectedCandidate}
            isArchiveView={isArchiveStatus(statusFilter) || categoryFilter === "archive"}
            lastCandidateRef={lastCandidateRef}
            onChange={reloadFirstPage}
          />

          <div className="mt-8 flex flex-col items-center gap-3" data-testid="candidates-load-more">
            {loadingMore && (
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Подгружаем ещё…
              </div>
            )}
            {hasMore && !loadingMore && (
              <button
                type="button"
                data-testid="candidates-load-more-btn"
                onClick={loadNextPage}
                className="px-5 py-2.5 rounded-xl border border-slate-200 bg-white text-sm font-medium text-slate-700 hover:bg-slate-50 shadow-sm"
              >
                Загрузить ещё
              </button>
            )}
            {!hasMore && candidates.length > 0 && (
              <p className="text-xs text-slate-400">Все кандидаты загружены</p>
            )}
          </div>
        </>
      )}

      {shownForm && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div
            className="bg-white p-0 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto ring-1 ring-slate-900/5"
            onClick={(e) => e.stopPropagation()}
          >
            <CandidateForm
              initialData={editingCandidate}
              onClose={handleCloseForm}
              onCandidateAdded={handleFormSuccess}
            />
          </div>
        </div>
      )}

      {selectedCandidate && (
        <div
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center z-50 p-4 sm:p-6"
          onClick={() => setSelectedCandidate(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden ring-1 ring-slate-900/5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-slate-100 shrink-0">
              <h2 className="text-lg font-bold text-slate-900">Карточка кандидата</h2>
              <button
                type="button"
                onClick={() => setSelectedCandidate(null)}
                className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-colors"
                aria-label="Закрыть"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-5 sm:p-6 overflow-y-auto flex-1">
              <CandidateDetails
                candidate={selectedCandidate}
                isArchiveView={isArchiveStatus(statusFilter) || categoryFilter === "archive"}
                onChange={reloadFirstPage}
              />
            </div>
          </div>
        </div>
      )}
    </MainLayout>
  );
}
