import { useEffect, useState } from "react";
import { createApproval, getApprovals } from "../../services/hrOpsApi";
import { useAlertContext } from "../../context/AlertContext";
import { useAuth } from "../../context/AuthContext";

const APPROVAL_STATUSES = [
    "Одобрен рекрутером",
    "Одобрен руководителем",
    "Одобрен собственником",
];

export default function ApprovalsSection({ candidateId, vacancyId, onApproved }) {
    const { showAlert } = useAlertContext();
    const { user } = useAuth();
    const [items, setItems] = useState([]);
    const [status, setStatus] = useState(APPROVAL_STATUSES[0]);
    const [comments, setComments] = useState("");
    const [saving, setSaving] = useState(false);

    const load = async () => {
        if (!candidateId) return;
        try {
            const data = await getApprovals({ candidateId, vacancyId });
            setItems(Array.isArray(data) ? data : []);
        } catch (e) {
            showAlert(`Не удалось загрузить согласования: ${e.message || e}`, "error");
        }
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [candidateId, vacancyId]);

    const handleSubmit = async () => {
        if (!vacancyId) {
            showAlert("Нет активной вакансии для согласования", "warning");
            return;
        }
        if (!user?.id && !user?.erp_user_id) {
            showAlert("Не удалось определить текущего пользователя", "error");
            return;
        }
        try {
            setSaving(true);
            await createApproval({
                vacancy_id: Number(vacancyId),
                candidate_id: Number(candidateId),
                approver_id: String(user.erp_user_id || user.id),
                approver_name: user.full_name || user.username || user.login || null,
                new_status: status,
                comments: comments.trim(),
            });
            showAlert("Согласование сохранено", "success");
            setComments("");
            await load();
            onApproved?.();
        } catch (e) {
            showAlert(`Ошибка согласования: ${e.message || e}`, "error");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="bg-white p-4 rounded-xl border border-slate-200/60 shadow-sm mt-6 space-y-4">
            <h3 className="font-semibold text-lg text-slate-900">Согласования</h3>

            <div className="space-y-2 max-h-40 overflow-y-auto text-sm">
                {items.length === 0 ? (
                    <p className="text-slate-400">Согласований пока нет.</p>
                ) : (
                    items.map((a) => (
                        <div key={a.id} className="border-b border-slate-100 pb-2">
                            <div className="font-medium text-slate-800">{a.new_status}</div>
                            {a.comments && <div className="text-slate-600">{a.comments}</div>}
                            <div className="text-xs text-slate-400">
                                {a.approver_name || (a.approver_id ? `#${a.approver_id}` : "Сотрудник")} · {a.created_at ? new Date(a.created_at).toLocaleString("ru-RU") : ""}
                            </div>
                        </div>
                    ))
                )}
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="border border-slate-200 rounded-xl px-3 py-2 text-sm"
                >
                    {APPROVAL_STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                    ))}
                </select>
                <input
                    value={comments}
                    onChange={(e) => setComments(e.target.value)}
                    placeholder="Комментарий к согласованию"
                    className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm"
                />
                <button
                    type="button"
                    disabled={saving}
                    onClick={handleSubmit}
                    className="bg-[#e0bb48] text-black px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50"
                >
                    {saving ? "..." : "Согласовать"}
                </button>
            </div>
        </div>
    );
}
