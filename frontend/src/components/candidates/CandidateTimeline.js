import { useCallback, useEffect, useMemo, useState } from "react";
import {
    createApproval,
    createCandidateComment,
    deleteCandidateComment,
    getApprovals,
    getCandidateComments,
    getCandidateStageHistory,
} from "../../services/hrOpsApi";
import { useAlertContext } from "../../context/AlertContext";
import { useAuth } from "../../context/AuthContext";
import { formatRuDateTime, mergeCandidateTimeline } from "../../utils/candidateActivity";

const APPROVAL_DECISIONS = [
    "Одобрен рекрутером",
    "Одобрен руководителем",
    "Одобрен собственником",
];

const FILTERS = [
    { id: "all", label: "Все" },
    { id: "status", label: "Статусы" },
    { id: "comment", label: "Комментарии" },
    { id: "approval", label: "Согласования" },
];

const TYPE_META = {
    status: { label: "Статус", className: "bg-sky-50 text-sky-800 ring-sky-200" },
    comment: { label: "Комментарий", className: "bg-slate-100 text-slate-700 ring-slate-200" },
    approval: { label: "Согласование", className: "bg-amber-50 text-amber-900 ring-amber-200" },
};

function currentUserIds(user) {
    if (!user) return { id: "", name: "" };
    return {
        id: String(user.erp_user_id || user.id || "").trim(),
        name: String(user.full_name || user.name || user.username || user.login || "").trim(),
    };
}

export default function CandidateTimeline({ candidateId, vacancyId, refreshKey, onChanged }) {
    const { showAlert } = useAlertContext();
    const { user } = useAuth();
    const [history, setHistory] = useState([]);
    const [comments, setComments] = useState([]);
    const [approvals, setApprovals] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState("all");
    const [commentText, setCommentText] = useState("");
    const [savingComment, setSavingComment] = useState(false);
    const [decision, setDecision] = useState(APPROVAL_DECISIONS[0]);
    const [approvalNote, setApprovalNote] = useState("");
    const [savingApproval, setSavingApproval] = useState(false);

    const load = useCallback(async () => {
        if (!candidateId) return;
        setLoading(true);
        try {
            const [hist, comm, appr] = await Promise.all([
                getCandidateStageHistory(candidateId),
                getCandidateComments(candidateId),
                getApprovals({ candidateId, vacancyId }),
            ]);
            setHistory(Array.isArray(hist) ? hist : []);
            setComments(Array.isArray(comm) ? comm : []);
            setApprovals(Array.isArray(appr) ? appr : []);
        } catch (error) {
            showAlert("Не удалось загрузить историю кандидата: " + (error.message || error), "error");
        } finally {
            setLoading(false);
        }
    }, [candidateId, vacancyId, showAlert]);

    useEffect(() => {
        load();
    }, [load, refreshKey]);

    const events = useMemo(
        () => mergeCandidateTimeline({ history, comments, approvals }),
        [history, comments, approvals]
    );
    const visible = filter === "all" ? events : events.filter((item) => item.type === filter);

    const handleAddComment = async () => {
        if (!commentText.trim()) return;
        const { id, name } = currentUserIds(user);
        try {
            setSavingComment(true);
            await createCandidateComment(candidateId, {
                body: commentText.trim(),
                author_id: id || null,
                author_name: name || null,
            });
            setCommentText("");
            await load();
            showAlert("Комментарий добавлен", "success");
        } catch (error) {
            showAlert("Ошибка добавления комментария: " + (error.message || error), "error");
        } finally {
            setSavingComment(false);
        }
    };

    const handleDeleteComment = async (commentId) => {
        if (!window.confirm("Удалить комментарий?")) return;
        try {
            await deleteCandidateComment(candidateId, commentId);
            await load();
        } catch (error) {
            showAlert("Не удалось удалить: " + (error.message || error), "error");
        }
    };

    const handleApprove = async () => {
        if (!vacancyId) {
            showAlert("Нет активной вакансии для согласования", "warning");
            return;
        }
        const { id, name } = currentUserIds(user);
        if (!id) {
            showAlert("Не удалось определить текущего пользователя", "error");
            return;
        }
        try {
            setSavingApproval(true);
            await createApproval({
                vacancy_id: Number(vacancyId),
                candidate_id: Number(candidateId),
                approver_id: id,
                approver_name: name || null,
                new_status: decision,
                comments: approvalNote.trim(),
            });
            setApprovalNote("");
            await load();
            onChanged?.();
            showAlert("Согласование сохранено", "success");
        } catch (error) {
            showAlert(`Ошибка согласования: ${error.message || error}`, "error");
        } finally {
            setSavingApproval(false);
        }
    };

    return (
        <section className="rounded-2xl border border-slate-200/80 bg-white p-5 space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        История работы с кандидатом
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                        Кто менял статус, оставлял комментарии и согласовывал карточку.
                    </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                    {FILTERS.map((item) => (
                        <button
                            key={item.id}
                            type="button"
                            onClick={() => setFilter(item.id)}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium ${
                                filter === item.id
                                    ? "bg-slate-900 text-white"
                                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                            }`}
                        >
                            {item.label}
                        </button>
                    ))}
                </div>
            </div>

            {loading ? (
                <p className="text-sm text-slate-400">Загрузка истории…</p>
            ) : visible.length === 0 ? (
                <p className="text-sm text-slate-400">Пока нет записей — действия появятся здесь.</p>
            ) : (
                <ol className="relative space-y-0 border-l border-slate-200 ml-2.5">
                    {visible.map((event) => {
                        const meta = TYPE_META[event.type] || TYPE_META.comment;
                        const commentId = event.type === "comment" ? event.raw?.id : null;
                        return (
                            <li key={event.id} className="relative pl-6 pb-5 last:pb-0">
                                <span className="absolute -left-[7px] top-1.5 h-3.5 w-3.5 rounded-full bg-white ring-2 ring-slate-300" />
                                <div className="flex flex-wrap items-center gap-2 mb-1">
                                    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ring-1 ${meta.className}`}>
                                        {meta.label}
                                    </span>
                                    <time className="text-xs text-slate-400">{formatRuDateTime(event.at)}</time>
                                </div>
                                <p className="text-sm font-medium text-slate-800 leading-snug">{event.title}</p>
                                {event.detail ? (
                                    <p className="mt-1 text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
                                        {event.detail}
                                    </p>
                                ) : null}
                                {commentId ? (
                                    <button
                                        type="button"
                                        onClick={() => handleDeleteComment(commentId)}
                                        className="mt-1 text-xs text-rose-500 hover:text-rose-700"
                                    >
                                        Удалить комментарий
                                    </button>
                                ) : null}
                            </li>
                        );
                    })}
                </ol>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                <div>
                    <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-2">Новый комментарий</p>
                    <div className="flex gap-2">
                        <textarea
                            value={commentText}
                            onChange={(e) => setCommentText(e.target.value)}
                            placeholder="Что произошло, о чём договорились, почему решение…"
                            rows={3}
                            className="flex-1 border border-slate-200 px-3 py-2 rounded-xl text-sm resize-y min-h-[76px]"
                        />
                    </div>
                    <button
                        type="button"
                        onClick={handleAddComment}
                        disabled={savingComment || !commentText.trim()}
                        className="mt-2 bg-slate-900 text-white px-4 py-2 text-sm rounded-xl disabled:opacity-50"
                    >
                        {savingComment ? "Сохранение…" : "Добавить комментарий"}
                    </button>
                </div>
                <div>
                    <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-2">Согласование</p>
                    {!vacancyId ? (
                        <p className="text-sm text-slate-400">Привяжите вакансию, чтобы согласовать кандидата.</p>
                    ) : (
                        <>
                            <div className="flex flex-col gap-2">
                                <select
                                    value={decision}
                                    onChange={(e) => setDecision(e.target.value)}
                                    className="border border-slate-200 rounded-xl px-3 py-2 text-sm"
                                >
                                    {APPROVAL_DECISIONS.map((item) => (
                                        <option key={item} value={item}>{item}</option>
                                    ))}
                                </select>
                                <input
                                    value={approvalNote}
                                    onChange={(e) => setApprovalNote(e.target.value)}
                                    placeholder="Комментарий к решению (необязательно)"
                                    className="border border-slate-200 rounded-xl px-3 py-2 text-sm"
                                />
                            </div>
                            <button
                                type="button"
                                disabled={savingApproval}
                                onClick={handleApprove}
                                className="mt-2 bg-[#e0bb48] text-black px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50"
                            >
                                {savingApproval ? "Сохранение…" : "Зафиксировать согласование"}
                            </button>
                        </>
                    )}
                </div>
            </div>
        </section>
    );
}
