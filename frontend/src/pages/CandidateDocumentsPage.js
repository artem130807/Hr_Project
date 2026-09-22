import { useCallback, useEffect, useState } from "react";
import MainLayout from "../layout/MainLayout";
import { completeCandidateDocuments, listCandidateDocuments } from "../services/candidateDocumentsApi";
import { useAlertContext } from "../context/AlertContext";
import { CANDIDATE_DOCUMENT_LABELS } from "../config/candidateDocumentTypes";

export default function CandidateDocumentsPage() {
    const [items, setItems] = useState([]); const [loading, setLoading] = useState(true); const { showAlert } = useAlertContext();
    const load = useCallback(async () => { try { setLoading(true); setItems(await listCandidateDocuments()); } catch (e) { showAlert(e.message, "error"); } finally { setLoading(false); } }, [showAlert]);
    useEffect(() => { load(); }, [load]);
    const complete = async (id) => { if (!window.confirm("Подтвердить, что все необходимые документы на месте?")) return; try { await completeCandidateDocuments(id); await load(); showAlert("Установлен статус «Полный пакет документов»", "success"); } catch (e) { showAlert(e.message, "error"); } };
    return <MainLayout><h1 className="text-3xl font-bold">Документы кандидатов</h1><p className="mt-1 text-slate-500">Пакеты документов, отправленные кандидатами после оффера.</p><div className="mt-6 space-y-4">{loading ? <p>Загрузка…</p> : null}{!loading && !items.length ? <p className="rounded-xl border bg-white p-5 text-slate-500">Отправленных пакетов пока нет.</p> : null}{items.map((item) => <section key={item.id} className="rounded-2xl border bg-white p-5"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-lg font-semibold">{item.candidate.full_name}</h2><p className="text-sm text-slate-500">Отправлено: {new Date(item.submitted_at).toLocaleString("ru-RU")} · {item.status === "complete" ? "Полный пакет" : "Ожидает проверки"}</p></div>{item.status !== "complete" ? <button className="rounded-xl bg-green-700 px-4 py-2 text-sm text-white" onClick={() => complete(item.id)}>Полный пакет документов</button> : null}</div><div className="mt-4 grid gap-2 md:grid-cols-2">{item.documents.map((document) => <a key={document.key} href={document.url} target="_blank" rel="noreferrer" className="rounded-xl border p-3 hover:bg-slate-50"><b>{CANDIDATE_DOCUMENT_LABELS[document.kind] || document.kind}</b><p className="truncate text-xs text-slate-500">{document.filename}</p></a>)}</div></section>)}</div></MainLayout>;
}
