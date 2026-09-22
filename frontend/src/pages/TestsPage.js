import React, { useEffect, useState } from 'react';
import {getTests, deleteTest, getTest} from "../services/testApi";
import TestForm from '../components/tests/TestForm';
import TestList from '../components/tests/TestList';
import PsychInstrumentCatalog from '../components/tests/PsychInstrumentCatalog';
import {useAlertContext} from "../context/AlertContext";
import MainLayout from "../layout/MainLayout";
import TestDetails from "../components/tests/TestDetails";

const TestsPage = () => {
    const [tests, setTests] = useState([]);
    const [showForm, setShowForm] = useState(false);
    const [editingTest, setEditingTest] = useState(null);
    const [loading, setLoading] = useState(false);
    const {showAlert} = useAlertContext()
    const [selectedTest, setSelectedTest] = useState(null);

    const fetchTests = async () => {
        try {
            const data = await getTests()
            const normalized = Array.isArray(data) ? data : (data?.items || data?.data || []);
            const sorted = [...normalized].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
            setTests(sorted)
        } catch (e) {
            console.error("Ошибка загрузки тестов", e)
            showAlert("Ошибка при загрузки тестов: " + (e.message || "Unknown error"), "error")
            setTests([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleAddTest = () => {
        setEditingTest(null);
        setShowForm(true);
    }

    const handleTestClick = async (test) => {
        try {
            const full = test?.id ? await getTest(test.id) : null;
            setSelectedTest(full || test);
        } catch (e) {
            console.error("Ошибка загрузки теста", e);
            setSelectedTest(test);
        }
    };

    const handleTestEdit = async (test) => {
        // Prefer full GET so questions are always present (list can be stale after save)
        try {
            const full = test?.id ? await getTest(test.id) : null;
            setEditingTest(full || test);
        } catch (e) {
            console.error("Ошибка загрузки теста для редактирования", e);
            setEditingTest(test);
        }
        setShowForm(true);
    }

    const handleTestDeleted = async (id) => {
        if(!window.confirm("Удалить тест?")) return;

        try {
            await deleteTest(id)
            setTests((prev) => prev.filter((t) => t.id !== id))
            showAlert("Тест удален", "success")
        } catch (e) {
            console.error("Ошибка при удалении: ", e)
            showAlert(`Ошибка при удалении ${e.message || "Unknown error"}`, "error")
        }
    }

    const handleFormSuccess = (saved) => {
        if(saved?.id) {
            setTests((prev) => {
                const exists = prev.some((t) => t.id === saved.id)
                const next = exists ? prev.map((t) => (t.id === saved.id ? saved : t)) : [...prev, saved];
                return next;
                }
            )
        }
        fetchTests()
        setShowForm(false);
        setEditingTest(null);
    }

    const handleCloseForm = () => {
        setShowForm(false);
        setEditingTest(null);
    }

    if(loading) return <MainLayout><p>Загрузка...</p></MainLayout>

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <div className="mb-6 space-y-6">
                <div className="flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Создание тестов</h1>
                        <p className="mt-1 text-sm text-slate-500">
                            Библиотека профессиональных тестов и готовые психологические опросники со ссылкой для прохождения.
                        </p>
                    </div>
                    <button 
                        onClick={handleAddTest} 
                        className="bg-slate-900 text-white px-4 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center gap-2"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                        Добавить тест
                    </button>
                </div>
            </div>

            <TestList 
                tests={tests} 
                onTestDeleted={handleTestDeleted} 
                onTestEdit={handleTestEdit} 
                onTestClick={handleTestClick}
                psychCatalog={<PsychInstrumentCatalog />}
            />

            {showForm && (
                <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center z-50 p-4" onClick={handleCloseForm}>
                    <div className="bg-white p-0 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto ring-1 ring-slate-900/5" onClick={(e) => e.stopPropagation()}>
                        <TestForm initialData={editingTest} onClose={handleCloseForm} onTestAdded={handleFormSuccess}/>
                    </div>
                </div>
            )}

            {selectedTest && (
                <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center z-50 p-4" onClick={() => setSelectedTest(null)}>
                    <div className="bg-white p-0 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto ring-1 ring-slate-900/5" onClick={(e) => e.stopPropagation()}>
                        <div className="p-6">
                            <TestDetails test={selectedTest} onClose={() => setSelectedTest(null)} />
                        </div>
                    </div>
                </div>
            )}
        </MainLayout>
    );
};

export default TestsPage;