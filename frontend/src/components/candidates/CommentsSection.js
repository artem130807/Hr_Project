import { useEffect, useState, useCallback } from "react";
import {
    getCandidateComments,
    createCandidateComment,
    deleteCandidateComment,
} from "../../services/hrOpsApi";
import { useAlertContext } from "../../context/AlertContext";
import { useAuth } from "../../context/AuthContext";

export default function CommentsSection({ candidateId }) {
    const [comments, setComments] = useState([]);
    const [text, setText] = useState("");
    const [saving, setSaving] = useState(false);
    const { showAlert } = useAlertContext();
    const { user } = useAuth();

    const fetchComments = useCallback(async () => {
        if (!candidateId) return;
        try {
            const data = await getCandidateComments(candidateId);
            setComments(Array.isArray(data) ? data : []);
        } catch (error) {
            showAlert("Ошибка загрузки комментариев: " + (error.message || error), "error");
        }
    }, [candidateId, showAlert]);

    useEffect(() => {
        fetchComments();
    }, [fetchComments]);

    const handleAddComment = async () => {
        if (!text.trim()) return;
        try {
            setSaving(true);
            await createCandidateComment(candidateId, {
                body: text.trim(),
                author_id: user?.erp_user_id || user?.id || null,
                author_name: user?.full_name || user?.username || user?.login || null,
            });
            setText("");
            await fetchComments();
            showAlert("Комментарий добавлен", "success");
        } catch (error) {
            showAlert("Ошибка добавления комментария: " + (error.message || error), "error");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Удалить комментарий?")) return;
        try {
            await deleteCandidateComment(candidateId, id);
            await fetchComments();
        } catch (error) {
            showAlert("Не удалось удалить: " + (error.message || error), "error");
        }
    };

    return (
        <div className="bg-white p-4 rounded-xl border border-slate-200/60 shadow-sm mt-6 space-y-4">
            <h3 className="font-semibold text-lg text-slate-900">Комментарии</h3>

            <div className="space-y-2 max-h-48 overflow-y-auto">
                {comments.length === 0 && (
                    <p className="text-sm text-slate-400">Комментариев пока нет.</p>
                )}
                {comments.map((c) => (
                    <div key={c.id} className="border-b border-slate-100 pb-2 text-sm flex justify-between gap-2">
                        <div>
                            <div className="text-slate-800">{c.body}</div>
                            <div className="text-xs text-slate-400">
                                {c.author_name ? `${c.author_name} · ` : ""}
                                {c.created_at ? new Date(c.created_at).toLocaleString("ru-RU") : ""}
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => handleDelete(c.id)}
                            className="text-xs text-red-500 hover:text-red-700 shrink-0"
                        >
                            Удалить
                        </button>
                    </div>
                ))}
            </div>

            <div className="flex gap-2">
                <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Добавить комментарий..."
                    className="flex-1 border border-slate-200 px-3 py-2 rounded-xl text-sm"
                />
                <button
                    type="button"
                    onClick={handleAddComment}
                    disabled={saving}
                    className="bg-slate-900 text-white px-4 py-2 text-sm rounded-xl disabled:opacity-50"
                >
                    Добавить
                </button>
            </div>
        </div>
    );
}
