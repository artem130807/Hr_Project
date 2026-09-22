import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import RequestFormModal from "../components/requests/RequestFormModal";
import { getPublicHiringRequestInvite, submitPublicHiringRequest } from "../services/hiringRequestsApi";

export default function HiringRequestPublicPage() {
    const { token } = useParams();
    const [invite, setInvite] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [created, setCreated] = useState(null);

    const load = useCallback(async () => {
        try {
            setLoading(true);
            setError("");
            setInvite(await getPublicHiringRequestInvite(token));
        } catch (loadError) {
            setInvite(null);
            setError(loadError.message);
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => { load(); }, [load]);

    const submit = async (payload) => {
        try {
            setSubmitting(true);
            setError("");
            setCreated(await submitPublicHiringRequest(token, payload));
        } catch (submitError) {
            setError(submitError.message);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return <main className="min-h-screen bg-slate-100 flex items-center justify-center p-6 text-slate-600">Проверяем ссылку…</main>;
    if (created) return <main className="min-h-screen bg-slate-100 flex items-center justify-center p-6"><section className="max-w-lg rounded-3xl bg-white p-8 text-center shadow-xl"><h1 className="text-2xl font-bold text-slate-900">Заявка отправлена</h1><p className="mt-3 text-slate-600">Номер заявки: <b>{created.public_code}</b>. HR получил заявку и возьмёт её в работу.</p></section></main>;
    if (!invite) return <main className="min-h-screen bg-slate-100 flex items-center justify-center p-6"><section className="max-w-lg rounded-3xl bg-white p-8 text-center shadow-xl"><h1 className="text-2xl font-bold text-slate-900">Ссылка недоступна</h1><p className="mt-3 text-red-700">{error || "Ссылка уже использована или срок её действия истёк."}</p><button type="button" onClick={load} className="mt-5 rounded-xl bg-slate-900 px-4 py-2 text-white">Попробовать снова</button></section></main>;

    return (
        <main className="min-h-screen bg-slate-100">
            {error ? <div className="fixed left-1/2 top-3 z-[60] -translate-x-1/2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 shadow">{error}</div> : null}
            <RequestFormModal publicMode closable={false} onSubmit={submit} isLoading={submitting} />
        </main>
    );
}
