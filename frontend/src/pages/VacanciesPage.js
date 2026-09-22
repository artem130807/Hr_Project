import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getVacancies, deleteVacancy } from "../services/vacancyApi";
import VacancyList from "../components/vacancies/VacancyList";
import VacancyForm from "../components/vacancies/VacancyForm";
import VacancyFilterStepModal from "../components/vacancies/VacancyFilterStepModal";
import MainLayout from "../layout/MainLayout";
import { useAlertContext } from "../context/AlertContext";
import { useAuth } from "../context/AuthContext";
import { mapVacancyFromBackend } from "../utils/vacancyMapper";
import HHEmployerVacanciesPanel from "../components/hh/HHEmployerVacanciesPanel";
import HHNegotiationsModal from "../components/hh/HHNegotiationsModal";
import { DEPARTMENTS } from "../config/api";

export default function VacanciesPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [vacancies, setVacancies] = useState([]);
    const [showForm, setShowForm] = useState(false);
    const [editingVacancy, setEditingVacancy] = useState(null);
    const [filterStepVacancy, setFilterStepVacancy] = useState(null);
    const [filterStepAllowSkip, setFilterStepAllowSkip] = useState(true);
    const [loading, setLoading] = useState(false);
    const [showHidden, setShowHidden] = useState(false);
    const tab = searchParams.get("tab") === "hh" ? "hh" : "local";
    const setTab = (next) => {
        const params = new URLSearchParams(searchParams);
        if (next === "hh") params.set("tab", "hh");
        else params.delete("tab");
        setSearchParams(params, { replace: true });
    };
    const [negotiationsFor, setNegotiationsFor] = useState(null);
    const { showAlert } = useAlertContext();
    const { user } = useAuth();

    const fetchVacancies = async () => {
        try {
            setLoading(true);
            const department = user?.role === "lead" && user?.department ? user.department : null;
            const data = await getVacancies(department);
            const mappedData = Array.isArray(data) ? data.map((vacancy) => mapVacancyFromBackend(vacancy)) : [];
            const sorted = mappedData.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
            setVacancies(sorted);
        } catch (e) {
            console.error("Ошибка загрузки", e);
            showAlert(`Ошибка загрузки вакансий: ${e.message || "Unknown error"}`, "error");
            setVacancies([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (user) {
            fetchVacancies();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user]);

    const handleAddVacancy = () => {
        setEditingVacancy(null);
        setShowForm(true);
    };

    const handleVacancyEdit = (vacancy) => {
        setEditingVacancy(vacancy);
        setShowForm(true);
    };

    const handleVacancyDeleted = async (vacancyOrId) => {
        const vacancy =
            typeof vacancyOrId === "object" && vacancyOrId !== null
                ? vacancyOrId
                : vacancies.find((v) => v.id === vacancyOrId);
        const id = vacancy?.id ?? vacancyOrId;

        if (!window.confirm("Удалить вакансию только из HR-платформы? Публикация на HH.ru останется без изменений.")) return;

        if (!id) {
            showAlert("Ошибка: ID вакансии не определен", "error");
            return;
        }

        try {
            await deleteVacancy(id);
            setVacancies((prev) => prev.filter((v) => v.id !== id));
            showAlert("Вакансия удалена из HR-платформы; публикация HH не изменена", "success");
        } catch (e) {
            console.error("Ошибка при удалении", e);
            showAlert(`Ошибка при удалении: ${e.message || "Unknown error"}`, "error");
        }
    };

    const handleFormSuccess = (saved) => {
        const isNewVacancy = !editingVacancy?.id;
        if (saved?.id) {
            setVacancies((prev) => {
                const exists = prev.some((v) => v.id === saved.id);
                return exists
                    ? prev.map((v) => (v.id === saved.id ? saved : v))
                    : [saved, ...prev];
            });
        }
        fetchVacancies();
        setShowForm(false);
        setEditingVacancy(null);
        // After create — offer filter select/create (can be skipped)
        if (isNewVacancy && saved?.id) {
            setFilterStepAllowSkip(true);
            setFilterStepVacancy(saved);
        }
    };

    const handleManageFilter = (vacancy) => {
        setFilterStepAllowSkip(false);
        setFilterStepVacancy(vacancy);
    };

    const handleCloseForm = () => {
        setShowForm(false);
        setEditingVacancy(null);
    };

    const handleFilterStepDone = (updatedVacancy) => {
        if (updatedVacancy?.id) {
            setVacancies((prev) =>
                prev.map((v) => (v.id === updatedVacancy.id ? { ...v, ...updatedVacancy } : v))
            );
        }
        setFilterStepVacancy(null);
        fetchVacancies();
    };

    const handleFilterStepSkip = () => {
        setFilterStepVacancy(null);
    };

    if (loading && tab === "local") {
        return (
            <MainLayout>
                <p>Загрузка...</p>
            </MainLayout>
        );
    }

    return (
        <MainLayout className="p-6">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Вакансии</h1>
                    <p className="mt-1 text-sm text-slate-500">Управление открытыми и архивными вакансиями.</p>
                </div>
                {tab === "local" && (
                    <button
                        type="button"
                        onClick={handleAddVacancy}
                        className="bg-slate-900 text-white px-4 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                        Добавить вакансию
                    </button>
                )}
            </div>

            <div className="flex gap-4 mb-6 border-b border-slate-200">
                <button
                    type="button"
                    onClick={() => setTab("local")}
                    className={`pb-3 px-2 text-sm font-medium transition-colors relative ${
                        tab === "local"
                            ? "text-[#4f46e5]"
                            : "text-slate-500 hover:text-slate-800"
                    }`}
                >
                    В платформе
                    {tab === "local" && (
                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4f46e5] rounded-t-full" />
                    )}
                </button>
                <button
                    type="button"
                    onClick={() => setTab("hh")}
                    className={`pb-3 px-2 text-sm font-medium transition-colors relative ${
                        tab === "hh"
                            ? "text-[#4f46e5]"
                            : "text-slate-500 hover:text-slate-800"
                    }`}
                >
                    С HH.ru
                    {tab === "hh" && (
                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4f46e5] rounded-t-full" />
                    )}
                </button>
            </div>

            {tab === "local" ? (
                <label className="mb-4 inline-flex items-center gap-2 text-sm text-slate-600">
                    <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} />
                    Показывать скрытые вакансии
                    <span className="text-slate-400">({vacancies.filter((v) => v.is_internal_hidden).length})</span>
                </label>
            ) : null}

            {tab === "local" ? (
                <VacancyList
                    vacancies={showHidden ? vacancies : vacancies.filter((v) => !v.is_internal_hidden)}
                    onVacancyDeleted={handleVacancyDeleted}
                    onVacancyEdit={handleVacancyEdit}
                    onManageFilter={handleManageFilter}
                    onOpenHHNegotiations={(vacancy) =>
                        setNegotiationsFor({
                            id: vacancy.hh_vacancy_id,
                            name: vacancy.name,
                        })
                    }
                    onVacancyUpdated={(updated) => {
                        setVacancies((prev) => {
                            const exists = prev.some((v) => v.id === updated.id);
                            if (exists) {
                                return prev.map((v) => (v.id === updated.id ? { ...v, ...updated } : v));
                            }
                            return [updated, ...prev];
                        });
                    }}
                />
            ) : (
                <HHEmployerVacanciesPanel
                    localVacancies={vacancies}
                    onLinked={fetchVacancies}
                    defaultDepartment={
                        user?.department && DEPARTMENTS.includes(user.department)
                            ? user.department
                            : undefined
                    }
                />
            )}

            {negotiationsFor?.id && (
                <HHNegotiationsModal
                    hhVacancyId={String(negotiationsFor.id)}
                    vacancyName={negotiationsFor.name}
                    onClose={() => setNegotiationsFor(null)}
                />
            )}

            {showForm && (
                <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-start z-50 overflow-y-auto py-8 px-4">
                    <div className="bg-white p-6 rounded-2xl shadow-xl w-full max-w-4xl ring-1 ring-slate-900/5">
                        <VacancyForm
                            initialData={editingVacancy}
                            onClose={handleCloseForm}
                            onVacancyAdded={handleFormSuccess}
                        />
                    </div>
                </div>
            )}

            {filterStepVacancy?.id && (
                <VacancyFilterStepModal
                    vacancy={filterStepVacancy}
                    allowSkip={filterStepAllowSkip}
                    onDone={handleFilterStepDone}
                    onSkip={handleFilterStepSkip}
                />
            )}
        </MainLayout>
    );
}
