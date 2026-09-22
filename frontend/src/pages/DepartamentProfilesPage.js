import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
    listDepartmentCandidateImages,
    createDepartmentCandidateImage,
    updateDepartmentCandidateImage,
} from "../services/candidateImageApi";
import { useAlertContext } from "../context/AlertContext";
import ProfileList from "../components/departments/ProfileList";
import ProfileForm from "../components/departments/ProfileForm";
import MainLayout from "../layout/MainLayout";
import { isLeaderRole } from "../config/navConfig";

const MANAGE_ROLES = new Set(["hr", "owner", "dev", "lead"]);

export default function DepartmentProfilesPage() {
    const { user } = useAuth();
    const [profiles, setProfiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [editorOpen, setEditorOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const { showAlert } = useAlertContext();

    const canManage = MANAGE_ROLES.has(user?.role) || isLeaderRole(user?.role);

    const fetchProfiles = async () => {
        try {
            setLoading(true);
            const data = await listDepartmentCandidateImages();
            if (!data) {
                setProfiles([]);
            } else {
                setProfiles(Array.isArray(data) ? data : [data]);
            }
        } catch (e) {
            console.error("Ошибка при загрузке профилей отделов", e);
            if (e?.response?.status !== 404 && !String(e?.message || "").includes("404")) {
                showAlert(
                    `Ошибка загрузки профилей отделов: ${e?.response?.data?.detail || e.message || "Unknown error"}`,
                    "error"
                );
            }
            setProfiles([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchProfiles();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.id, user?.role]);

    const openCreate = () => {
        setEditing(null);
        setEditorOpen(true);
    };

    const openEdit = (profile) => {
        setEditing(profile);
        setEditorOpen(true);
    };

    const closeEditor = () => {
        setEditing(null);
        setEditorOpen(false);
    };

    const handleSave = async (form) => {
        try {
            setSaving(true);
            if (editing?.id) {
                await updateDepartmentCandidateImage(editing.department, {
                    hard_skills: form.hard_skills,
                    experience: form.experience,
                    expirience: form.expirience,
                    common_requirements: form.common_requirements,
                });
                showAlert("Профиль отдела сохранён", "success");
            } else {
                const leadId = String(user?.erp_user_id || user?.id || "").trim();
                await createDepartmentCandidateImage({
                    department: form.department,
                    hard_skills: form.hard_skills,
                    experience: form.experience,
                    expirience: form.expirience,
                    common_requirements: form.common_requirements,
                    ...(leadId ? { lead_id: leadId } : {}),
                });
                showAlert("Профиль отдела создан", "success");
            }
            closeEditor();
            await fetchProfiles();
        } catch (e) {
            const msg = String(e?.message || e?.response?.data?.detail || "");
            if (e?.response?.status === 409 || /already exists/i.test(msg)) {
                showAlert("Профиль для этого отдела уже существует", "error");
            } else {
                showAlert(`Не удалось сохранить профиль отдела: ${msg || "ошибка"}`, "error");
            }
        } finally {
            setSaving(false);
        }
    };

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <div className="mb-6 space-y-6">
                <div className="flex justify-between items-center gap-4 flex-wrap">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Профили отделов</h1>
                        <p className="mt-1 text-sm text-slate-500">
                            Портреты идеальных кандидатов для отделов компании. Отдел в карточке сотрудника не обязателен — выберите его из списка.
                        </p>
                    </div>
                    {canManage && !editorOpen && (
                        <button
                            type="button"
                            onClick={openCreate}
                            className="bg-slate-900 text-white px-5 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium"
                            data-testid="department-profile-create"
                        >
                            Создать профиль
                        </button>
                    )}
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center items-center py-20 text-slate-400">
                    Загрузка профилей...
                </div>
            ) : (
                <>
                    {editorOpen && canManage && (
                        <ProfileForm
                            existing={editing}
                            takenDepartments={profiles.map((p) => p.department).filter(Boolean)}
                            onSubmit={handleSave}
                            onCancel={closeEditor}
                            saving={saving}
                        />
                    )}
                    <ProfileList
                        profiles={profiles}
                        onEdit={canManage ? openEdit : undefined}
                    />
                </>
            )}
        </MainLayout>
    );
}
