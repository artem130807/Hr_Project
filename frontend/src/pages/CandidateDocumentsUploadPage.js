import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { CANDIDATE_DOCUMENT_LABELS, CANDIDATE_DOCUMENT_TYPES } from "../config/candidateDocumentTypes";
import {
    deleteCandidateDocumentDraftFile,
    getPublicCandidateDocumentsForm,
    openCandidateDocumentsUploadSession,
    submitPublicCandidateDocuments,
    uploadCandidateDocumentDraftFile,
} from "../services/candidateDocumentsApi";
import { CANDIDATE_DOCUMENT_DRAFT_CONTENT_TYPES, MAX_CANDIDATE_DOCUMENT_FILES } from "../utils/candidateDocumentsDraft";
import {
    clearCandidateDocumentSession, readCandidateDocumentSession, saveCandidateDocumentSession,
} from "../utils/candidateDocumentsSession";

const MAX_SOURCE_FILE_BYTES = 15 * 1024 * 1024;
function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error(`Не удалось прочитать ${file.name}`));
        reader.readAsDataURL(file);
    });
}

async function fileToUpload(file, kind) {
    if (!CANDIDATE_DOCUMENT_DRAFT_CONTENT_TYPES.has(file.type)) {
        throw new Error(`Формат файла «${file.name}» не поддерживается`);
    }
    if (!file.size || file.size > MAX_SOURCE_FILE_BYTES) {
        throw new Error(`Файл «${file.name}» пустой или превышает 15 МБ`);
    }
    let preparedFile = file;
    if (file.type.startsWith("image/") && file.type !== "image/gif") {
        const dataUrl = await readFile(file);
        preparedFile = await new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = () => {
                const scale = Math.min(1, 1600 / Math.max(image.width, image.height));
                const canvas = document.createElement("canvas");
                canvas.width = Math.max(1, Math.round(image.width * scale));
                canvas.height = Math.max(1, Math.round(image.height * scale));
                const context = canvas.getContext("2d");
                if (!context) {
                    reject(new Error(`Не удалось обработать ${file.name}`));
                    return;
                }
                context.drawImage(image, 0, 0, canvas.width, canvas.height);
                canvas.toBlob((blob) => {
                    if (!blob) return reject(new Error(`Не удалось обработать ${file.name}`));
                    resolve(new File([blob], `${file.name.replace(/\.[^.]+$/, "") || "document"}.jpg`, { type: "image/jpeg" }));
                }, "image/jpeg", 0.82);
            };
            image.onerror = () => reject(new Error(`Не удалось прочитать ${file.name}`));
            image.src = dataUrl;
        });
    }
    return { kind, file: preparedFile };
}

export default function CandidateDocumentsUploadPage() {
    const { token } = useParams();
    const [info, setInfo] = useState(null);
    const [linkChecked, setLinkChecked] = useState(false);
    const [error, setError] = useState("");
    const [entries, setEntries] = useState([]);
    const [kind, setKind] = useState("passport");
    const [sending, setSending] = useState(false);
    const [complete, setComplete] = useState(false);
    const [sessionToken, setSessionToken] = useState("");

    const loadForm = useCallback(async () => {
        setLinkChecked(false);
        setError("");
        try {
            const result = await getPublicCandidateDocumentsForm(token);
            setInfo(result);
            // Remove Base64 drafts written by the previous implementation.
            try { localStorage.removeItem(`candidate-documents-draft:${token}`); } catch (_) { /* optional */ }
            const saved = readCandidateDocumentSession();
            let draft;
            try {
                draft = await openCandidateDocumentsUploadSession(token, saved);
            } catch (resumeError) {
                if (!saved) throw resumeError;
                clearCandidateDocumentSession();
                draft = await openCandidateDocumentsUploadSession(token);
            }
            const nextToken = draft.session_token || saved;
            if (!nextToken) throw new Error("Сервер не вернул токен загрузочной сессии");
            setSessionToken(nextToken);
            setEntries(draft.files || []);
            saveCandidateDocumentSession(nextToken);
        } catch (loadError) {
            setInfo(null);
            setError(loadError.message);
        } finally {
            setLinkChecked(true);
        }
    }, [token]);

    useEffect(() => { loadForm(); }, [loadForm]);

    const totalBytes = useMemo(
        () => entries.reduce((sum, item) => sum + Number(item.size || 0), 0),
        [entries],
    );

    const addFiles = async (event) => {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        if (!info || !files.length) return;
        try {
            if (entries.length + files.length > MAX_CANDIDATE_DOCUMENT_FILES) {
                throw new Error(`Можно приложить не более ${MAX_CANDIDATE_DOCUMENT_FILES} файлов`);
            }
            setSending(true);
            for (const file of files) {
                const prepared = await fileToUpload(file, kind);
                const uploaded = await uploadCandidateDocumentDraftFile(token, sessionToken, prepared);
                setEntries((current) => [...current, uploaded]);
            }
        } catch (addError) {
            setError(addError.message);
        } finally {
            setSending(false);
        }
    };

    const removeFile = async (item) => {
        try {
            setSending(true);
            setError("");
            await deleteCandidateDocumentDraftFile(token, sessionToken, item.file_id);
            setEntries((current) => current.filter((row) => row.file_id !== item.file_id));
        } catch (removeError) {
            setError(removeError.message);
        } finally {
            setSending(false);
        }
    };

    const submit = async () => {
        if (!entries.length || !window.confirm("Отправить пакет документов? После отправки изменить его самостоятельно будет нельзя.")) return;
        try {
            setSending(true);
            setError("");
            await submitPublicCandidateDocuments(token, sessionToken);
            clearCandidateDocumentSession();
            setEntries([]);
            setComplete(true);
        } catch (submitError) {
            setError(submitError.message);
        } finally {
            setSending(false);
        }
    };

    if (complete) {
        return <main className="min-h-screen bg-slate-50 p-6 flex items-center justify-center"><div className="max-w-lg rounded-2xl bg-white p-8 text-center shadow"><h1 className="text-2xl font-bold">Документы отправлены</h1><p className="mt-3 text-slate-600">HR проверит комплект. Эту страницу можно закрыть.</p></div></main>;
    }
    if (!linkChecked) {
        return <main className="min-h-screen bg-slate-50 p-6 flex items-center justify-center"><p className="text-slate-600">Проверяем персональную ссылку…</p></main>;
    }
    if (!info) {
        return <main className="min-h-screen bg-slate-50 p-6 flex items-center justify-center"><div className="max-w-lg rounded-2xl bg-white p-8 text-center shadow"><h1 className="text-2xl font-bold">Ссылка недоступна</h1><p className="mt-3 text-red-700">{error || "Срок действия ссылки истёк или она уже была использована."}</p><button type="button" onClick={loadForm} className="mt-5 rounded-xl bg-slate-900 px-4 py-2 text-white">Попробовать снова</button></div></main>;
    }

    return (
        <main className="min-h-screen bg-slate-50 p-4 md:p-8">
            <div className="mx-auto max-w-3xl rounded-2xl bg-white p-6 shadow-sm">
                <h1 className="text-2xl font-bold">Документы для трудоустройства</h1>
                <p className="mt-2 text-slate-600">{info.candidate.full_name}, приложите читаемые фотографии или PDF.</p>
                <div className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-950"><b>Важно:</b> все документы необходимо принести в оригинале в день трудоустройства.</div>
                <div className="mt-5 rounded-xl border p-4">
                    <h2 className="font-semibold">Список документов</h2>
                    <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-700">
                        {CANDIDATE_DOCUMENT_TYPES.filter((item) => item.value !== "other").map((item) => <li key={item.value}><span className="font-medium text-slate-900">{item.label}</span>{item.hint ? <span className="text-slate-500"> — {item.hint}</span> : null}</li>)}
                    </ol>
                </div>
                {error ? <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
                <div className="mt-6 flex flex-wrap gap-3">
                    <select aria-label="Тип документа" className="min-w-64 flex-1 rounded-xl border px-3 py-2" value={kind} onChange={(event) => setKind(event.target.value)}>{CANDIDATE_DOCUMENT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                    <label className="cursor-pointer rounded-xl bg-slate-900 px-4 py-2 text-white">Добавить файлы<input className="hidden" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf" onChange={addFiles} /></label>
                </div>
                <div className="mt-5 space-y-2">
                    {entries.map((item) => <div key={item.file_id} className="flex items-center justify-between rounded-xl border p-3"><div><b>{CANDIDATE_DOCUMENT_LABELS[item.kind] || item.kind}</b><p className="text-xs text-slate-500">{item.filename} · {(item.size / 1024).toFixed(0)} КБ</p></div><button disabled={sending} type="button" className="text-sm text-red-700" onClick={() => removeFile(item)}>Удалить</button></div>)}
                </div>
                <p className="mt-4 text-xs text-slate-500">Файлы сохраняются в защищённом черновике на 72 часа и восстановятся после повторного открытия страницы. Для одного документа можно приложить несколько страниц. Загружено: {(totalBytes / 1024 / 1024).toFixed(2)} МБ.</p>
                <button type="button" disabled={!entries.length || sending} onClick={submit} className="mt-5 w-full rounded-xl bg-[#e0bb48] px-4 py-3 font-semibold disabled:opacity-50">{sending ? "Отправляем…" : "Отправить пакет документов"}</button>
            </div>
        </main>
    );
}
