import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import MainLayout from "../layout/MainLayout";
import { useAlertContext } from "../context/AlertContext";
import { useAuth } from "../context/AuthContext";
import {
    finalizeAdaptationCheckpoint,
    forceCompleteAdaptationCheckpoint,
    generateAdaptationDocuments,
    getAdaptationCheckpoint,
    rescheduleAdaptationCheckpoint,
    submitAdaptationAnswer,
} from "../services/adaptationApi";
import { MOCK_ADAPTATION_ITEMS } from "../data/mockAdaptation";
import AdaptationQuestionFields from "../adaptation/AdaptationQuestionFields";
import { formFor, formPublicTitle, normalizeQuestionnaire } from "../adaptation/catalog";
import { formatDateRu, ROLE_EMPLOYEE, ROLE_HR, ROLE_MANAGER, rolesForKind } from "../adaptation/rules";
import { managerSafeReport } from "../adaptation/reports";
import AdaptationTakeLinks from "../adaptation/AdaptationTakeLinks";

const ROLE_TITLES = {
    [ROLE_EMPLOYEE]: "Сотрудник",
    [ROLE_MANAGER]: "Руководитель",
    [ROLE_HR]: "HR",
};

function fallbackCheckpoint(checkpointId) {
    return MOCK_ADAPTATION_ITEMS.find((i) => String(i.id) === String(checkpointId)) || null;
}

export default function AdaptationDetailPage() {
    const { checkpointId } = useParams();
    const navigate = useNavigate();
    const { showAlert } = useAlertContext();
    const { user } = useAuth() || {};
    const isHr = ["superadmin", "admin", "manager", "senior_manager", "hr", "owner", "dev", "tech_admin", "director"].includes(user?.role);
    const [row, setRow] = useState(() => fallbackCheckpoint(checkpointId));
    const [role, setRole] = useState(isHr ? ROLE_HR : ROLE_MANAGER);
    const [values, setValues] = useState({});
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const data = await getAdaptationCheckpoint(checkpointId);
                if (!cancelled && data?.id) setRow(data);
            } catch {
                if (!cancelled) setRow(fallbackCheckpoint(checkpointId));
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [checkpointId]);

    useEffect(() => {
        if (!row) return;
        const existing = (row.answers || []).find((a) => a.role === role);
        setValues(existing?.payload || {});
    }, [row, role]);

    if (!row) {
        return (
            <MainLayout>
                <p className="text-slate-500">Этап не найден.</p>
            </MainLayout>
        );
    }

    const participating = new Set(rolesForKind(row.kind));
    const questions = normalizeQuestionnaire(
        row.kind,
        role,
        (row.form && row.form[role]) || formFor(row.kind, role)
    );
    const title = (row.form_title && row.form_title[role]) || formPublicTitle(row.kind, role);
    const existing = (row.answers || []).find((a) => a.role === role);
    const locked = Boolean(existing) && role !== ROLE_HR;
    const safe = managerSafeReport(row);

    const onChange = (id, value) => setValues((prev) => ({ ...prev, [id]: value }));

    const onSubmit = async (e) => {
        e.preventDefault();
        if (!participating.has(role)) {
            showAlert("Эта роль не участвует в этапе", "error");
            return;
        }
        if (locked) {
            showAlert("Ответы уже отправлены и заблокированы", "error");
            return;
        }
        setSaving(true);
        try {
            const updated = await submitAdaptationAnswer(row.id, { role, payload: values });
            setRow(updated);
            showAlert("Ответы сохранены", "success");
        } catch (err) {
            showAlert(err.message || "Не удалось сохранить (проверьте API)", "error");
        } finally {
            setSaving(false);
        }
    };

    const refresh = async () => setRow(await getAdaptationCheckpoint(row.id));

    const reschedule = async () => {
        const planDate = window.prompt("Новая дата этапа (ГГГГ-ММ-ДД)", row.plan_date || "");
        if (!planDate) return;
        const reason = window.prompt("Причина переноса");
        if (!reason) return;
        try {
            await rescheduleAdaptationCheckpoint(row.id, { plan_date: planDate, reason });
            await refresh();
            showAlert("Этап перенесён, будущие напоминания перестроены", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const forceComplete = async () => {
        const reason = window.prompt("Причина принудительного завершения");
        if (!reason) return;
        try {
            await forceCompleteAdaptationCheckpoint(row.id, { reason });
            await refresh();
            showAlert("Этап завершён принудительно; поздние ответы останутся доступны", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const finalize = async () => {
        const comment = window.prompt("Комментарий HR к итогу", "") ?? "";
        try {
            await finalizeAdaptationCheckpoint(row.id, { outcome: row.outcome || "stable", risk: row.risk === "uncalculated" ? "low" : row.risk, comment });
            await refresh();
            showAlert("Итог этапа зафиксирован", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const generateDocuments = async () => {
        try {
            await generateAdaptationDocuments(row.id, { formats: ["docx", "pdf"], final: row.status === "completed" });
            showAlert("Версии документов DOCX и PDF сформированы", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <button type="button" className="text-sm text-slate-500 mb-4" onClick={() => navigate("/tests/adaptation")}>
                ← К списку адаптации
            </button>
            <div className="mb-6">
                <p className="text-xs font-semibold tracking-[0.16em] text-slate-400">ТЕСТЫ / АДАПТАЦИЯ</p>
                <h1 className="text-2xl font-bold" data-testid="adaptation-detail-title">{row.full_name}</h1>
                <p className="text-sm text-slate-500">
                    {row.position} · {title} · план {formatDateRu(row.plan_date)} · {row.status_label}
                </p>
                {row.enrollment_id ? (
                    <button
                        type="button"
                        className="mt-2 text-sm text-slate-600 underline"
                        onClick={() => navigate(`/tests/adaptation/case/${row.enrollment_id}`)}
                    >
                        Карточка сотрудника
                    </button>
                ) : null}
                {isHr ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button type="button" onClick={reschedule} className="text-sm px-3 py-1.5 rounded-lg border">Перенести</button>
                        <button type="button" onClick={forceComplete} className="text-sm px-3 py-1.5 rounded-lg border">Завершить принудительно</button>
                        <button type="button" onClick={finalize} className="text-sm px-3 py-1.5 rounded-lg border">Зафиксировать итог</button>
                        <button type="button" onClick={generateDocuments} className="text-sm px-3 py-1.5 rounded-lg border">Сформировать документы</button>
                    </div>
                ) : null}
            </div>

            <div className="grid lg:grid-cols-3 gap-4">
                <form onSubmit={onSubmit} className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/60 p-5 space-y-4">
                    <div className="flex gap-2">
                        {(isHr ? [ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_HR] : [ROLE_MANAGER]).map((r) => (
                            <button
                                key={r}
                                type="button"
                                disabled={!participating.has(r)}
                                onClick={() => setRole(r)}
                                className={`px-3 py-1.5 rounded-lg text-sm border ${
                                    role === r ? "bg-slate-900 text-white" : "bg-white"
                                } disabled:opacity-40`}
                            >
                                {ROLE_TITLES[r]}
                            </button>
                        ))}
                    </div>
                    {isHr && (row.form_links || []).length ? (
                        <div className="rounded-xl bg-slate-50 p-3">
                            <b className="mb-2 block text-sm text-slate-800">Ссылки для прохождения</b>
                            <AdaptationTakeLinks links={(row.form_links || []).map((item) => ({ ...item, kind_label: row.kind_label, plan_date: row.plan_date, checkpoint_id: row.id }))} employeeId={row.employee_id} fullName={row.full_name} />
                        </div>
                    ) : null}
                    {locked ? (
                        <p className="text-sm text-amber-700 bg-amber-50 rounded-xl px-3 py-2">
                            Ответы этой роли уже отправлены и заблокированы. HR может править свой комментарий.
                        </p>
                    ) : null}
                    <AdaptationQuestionFields
                        questions={questions}
                        values={values}
                        onChange={onChange}
                        coreHistory={row.core_history || {}}
                        disabled={locked}
                    />
                    <button
                        type="submit"
                        disabled={saving || locked || !participating.has(role) || questions.length === 0}
                        className="bg-slate-900 text-white px-4 py-2.5 rounded-xl text-sm disabled:opacity-50"
                        data-testid="save-answers"
                    >
                        Сохранить ответы
                    </button>
                </form>
                <aside className="space-y-3">
                    <div className="bg-white rounded-2xl border p-4">
                        <h2 className="font-medium text-sm mb-1">Итог / риск</h2>
                        <p className="font-semibold">{row.outcome}</p>
                        <p className="text-sm text-slate-500">Риск: {row.risk_label}</p>
                    </div>
                    <div className="bg-white rounded-2xl border p-4" data-testid="manager-safe">
                        <h2 className="font-medium text-sm mb-1">Для руководителя</h2>
                        <p className="text-sm text-slate-700">{safe.hr_notes}</p>
                    </div>
                </aside>
            </div>
        </MainLayout>
    );
}
