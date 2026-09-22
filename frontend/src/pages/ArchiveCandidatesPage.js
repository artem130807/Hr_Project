import { useEffect, useState, useMemo } from "react";
import MainLayout from "../layout/MainLayout";
import { useAlertContext } from "../context/AlertContext";
import { getArchivedCandidates, getCandidateStatus, getCandidatesStatuses, getCandidateActiveVacancy, getCandidateVacancies } from "../services/candidateApi";
import { getVacancies } from "../services/vacancyApi";
import CandidateList from "../components/candidates/CandidateList";
import CandidateDetails from "../components/candidates/CandidateDetails";

export default function ArchiveCandidatesPage() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showAlert } = useAlertContext();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [vacancyFilter, setVacancyFilter] = useState("");
  const [vacancies, setVacancies] = useState([]);
  const [statusDict, setStatusDict] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const fetchArchived = async () => {
    try {
      setLoading(true);

      const data = await getArchivedCandidates();

      const list = Array.isArray(data)
          ? data
          : (data?.items ?? data?.data ?? data?.results ?? data?.rows ?? []);

      // Подгружаем статус и вакансию для каждого кандидата
      const enriched = await Promise.all(
        list.map(async (candidate) => {
          let result = { ...candidate };

          // Статус
          try {
            const statusData = await getCandidateStatus(candidate.id);
            const value = (typeof statusData === 'object')
              ? (statusData?.status ?? statusData?.code ?? statusData?.name ?? null)
              : statusData;
            result.status = value ?? candidate.status;
          } catch {
            result.status = candidate.status || "отказ";
          }

          // Вакансия: пробуем active, потом все
          try {
            const vac = await getCandidateActiveVacancy(candidate.id);
            if (vac) {
              result.vacancy_id = vac.vacancy_id || vac.id;
              result.vacancy_name = vac.name || vac.vacancy_name || vac.title;
            }
          } catch {
            try {
              const data = await getCandidateVacancies(candidate.id);
              const arr = Array.isArray(data) ? data : (data?.items ?? []);
              const last = arr[arr.length - 1];
              if (last) {
                result.vacancy_id = last.vacancy_id || last.vacancy?.id || last.id;
                result.vacancy_name = last.vacancy?.name || last.name || last.vacancy_name;
              }
            } catch {}
          }

          return result;
        })
      );

      setCandidates(enriched);
    } catch (e) {
      console.error(e);
      showAlert(`Ошибка загрузки архива: ${e?.response?.data?.detail ?? e.message}`, "error");
      setCandidates([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArchived();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const data = await getVacancies();
        setVacancies(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error("Не удалось загрузить вакансии", e);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const list = await getCandidatesStatuses();
        setStatusDict(Array.isArray(list) ? list : []);
      } catch (e) {
        console.error("Не удалось загрузить статусы", e);
        setStatusDict([]);
      }
    })();
  }, []);

  const filteredCandidates = useMemo(() => {
    return candidates.filter(c => {
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!(c.full_name || "").toLowerCase().includes(q)) return false;
      }
      if (statusFilter && c.status !== statusFilter) return false;
      if (vacancyFilter) {
        if (String(c.vacancy_id ?? "") !== String(vacancyFilter)) return false;
      }
      return true;
    });
  }, [candidates, searchQuery, statusFilter, vacancyFilter]);

  const handleChildChanged = () => {
    fetchArchived();
  };

  if (loading) {
    return (
      <MainLayout>
        <p className="text-[#666666]">Загрузка…</p>
      </MainLayout>
    );
  }

    return (
      <MainLayout className="flex flex-col h-full overflow-y-auto">
        <div className="mb-6 space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">Архив кандидатов</h1>
              <p className="mt-1 text-sm text-slate-500">Кандидаты, по которым работа завершена.</p>
            </div>
          </div>
  
          <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200/60 flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Поиск</label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="ФИО, телефон..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all"
                />
                <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-slate-400">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                </div>
              </div>
            </div>
  
            <div className="w-full sm:w-48">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Статус</label>
              <div className="relative">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all appearance-none cursor-pointer"
                >
                  <option value="">Все статусы</option>
                  {statusDict.map(s => (
                    <option key={s.id} value={s.name}>{s.name}</option>
                  ))}
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </div>
              </div>
            </div>
  
            <div className="w-full sm:w-48">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Вакансия</label>
              <div className="relative">
                <select
                  value={vacancyFilter}
                  onChange={(e) => setVacancyFilter(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all appearance-none cursor-pointer"
                >
                  <option value="">Все вакансии</option>
                  {vacancies.map(v => (
                    <option key={v.id} value={v.id}>{v.name}</option>
                  ))}
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-slate-400">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </div>
              </div>
            </div>
          </div>
  
        {filteredCandidates.length === 0 ? (
            <div className="bg-white p-12 rounded-2xl shadow-sm border border-slate-200/60 text-center flex flex-col items-center">
                <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-400">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" /></svg>
                </div>
                <h3 className="text-lg font-medium text-slate-800">Ничего не найдено</h3>
                <p className="text-slate-500 mt-1">Попробуйте изменить параметры поиска или фильтры.</p>
            </div>
        ) : (
            <CandidateList
                candidates={filteredCandidates}
                onCandidateEdit={() => {}}
                onCandidateDelete={() => {}}
                onCandidateClick={setSelectedCandidate}
                onChange={handleChildChanged}
                isArchiveView={true}
            />
        )}
        </div>
  
        {selectedCandidate && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 sm:p-6" onClick={() => setSelectedCandidate(null)}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100">
                <h2 className="text-xl font-bold text-slate-900">Детали кандидата</h2>
                <button onClick={() => setSelectedCandidate(null)} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              
              <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                <CandidateDetails
                  candidate={selectedCandidate}
                  isArchiveView={true}
                  onChange={handleChildChanged}
                />
              </div>
            </div>
          </div>
        )}
      </MainLayout>
    );
  }
