import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import AdaptationQuestionFields from "../adaptation/AdaptationQuestionFields";
import { formatQuestionAnswer } from "../adaptation/answerFormat";
import { normalizeQuestionnaire } from "../adaptation/catalog";
import { isQuestionVisible } from "../adaptation/showIf";
import { rememberAdaptationTake } from "../adaptation/takeLinks";
import { formatDateRu } from "../adaptation/rules";
import { getPublicAdaptationForm, submitPublicAdaptationForm } from "../services/adaptationApi";

export default function AdaptationPublicFormPage() {
    const { token } = useParams();
    const [form, setForm] = useState(null);
    const [values, setValues] = useState({});
    const [state, setState] = useState("loading");
    const [message, setMessage] = useState("");

    useEffect(() => {
        let active = true;
        setState("loading");
        setForm(null);
        setValues({});
        setMessage("");
        getPublicAdaptationForm(token)
            .then((data) => {
                if (!active) return;
                const normalized = {
                    ...data,
                    questions: normalizeQuestionnaire(data.kind, data.role, data.questions),
                };
                setForm(normalized);
                rememberAdaptationTake({ ...normalized, token });
                setState(data.locked ? "done" : "ready");
            })
            .catch((error) => {
                if (!active) return;
                setMessage(error.message || "Ссылка недействительна");
                setState("error");
            });
        return () => { active = false; };
    }, [token]);

    const submit = async (event) => {
        event.preventDefault();
        if (state === "ready") {
            const missing = (form.questions || []).find((question) => {
                if (question.required === false) return false;
                if (!isQuestionVisible(question, values, form.core_history || {})) return false;
                const value = values[question.id];
                return value == null
                    || (typeof value === "string" && value.trim() === "")
                    || (Array.isArray(value) && value.length === 0);
            });
            if (missing) {
                setMessage(`Заполните обязательное поле: «${missing.text}»`);
                return;
            }
            setMessage("");
            setState("review");
            return;
        }
        setState("saving");
        try {
            await submitPublicAdaptationForm(token, values);
            rememberAdaptationTake({ ...form, token, submitted: true });
            setState("done");
            setMessage("Спасибо! Ответы сохранены и переданы HR.");
        } catch (error) {
            setState("ready");
            setMessage(error.message || "Не удалось отправить ответы");
        }
    };

    if (state === "loading") {
        return (
            <main className="min-h-screen grid place-items-center bg-[#f4f6fb] text-slate-600">
                Загрузка формы…
            </main>
        );
    }
    if (state === "error") {
        return (
            <main className="min-h-screen grid place-items-center bg-[#f4f6fb] px-4">
                <div className="max-w-md rounded-2xl border border-red-100 bg-white p-8 text-center shadow-sm">
                    <h1 className="text-xl font-semibold text-slate-900">Ссылка недоступна</h1>
                    <p className="mt-2 text-sm text-red-700">{message}</p>
                </div>
            </main>
        );
    }
    if (state === "done") {
        return (
            <main className="min-h-screen grid place-items-center bg-[#f4f6fb] px-4">
                <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
                    <p className="text-xs font-semibold tracking-[0.16em] text-[#cda834]">АДАПТАЦИЯ</p>
                    <h1 className="mt-2 text-xl font-semibold text-slate-900">Форма заполнена</h1>
                    <p className="mt-2 text-slate-500">{message || "Ответы уже были отправлены."}</p>
                </div>
            </main>
        );
    }

    if (state === "review") {
        return (
            <main className="min-h-screen bg-[#f4f6fb] px-4 py-8">
                <form onSubmit={submit} className="mx-auto max-w-3xl space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h1 className="text-2xl font-bold text-slate-900">Проверьте ответы перед отправкой</h1>
                    <p className="text-sm text-slate-500">
                        После подтверждения ответы сохранятся в карточке сотрудника и будут заблокированы.
                    </p>
                    <dl className="divide-y">
                        {(form.questions || [])
                            .filter((question) => isQuestionVisible(question, values, form.core_history || {}) && values[question.id] != null && values[question.id] !== "")
                            .map((question) => (
                                <div key={question.id} className="py-2">
                                    <dt className="text-xs text-slate-500">{question.text}</dt>
                                    <dd className="text-slate-800">{formatQuestionAnswer(question, values[question.id])}</dd>
                                </div>
                            ))}
                    </dl>
                    <div className="flex gap-2">
                        <button type="button" onClick={() => setState("ready")} className="rounded-xl border px-5 py-2.5">Вернуться</button>
                        <button className="rounded-xl bg-[#0c1835] px-5 py-2.5 text-white">Подтвердить и отправить</button>
                    </div>
                </form>
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-[#f4f6fb] px-4 py-8">
            <form onSubmit={submit} className="mx-auto max-w-3xl space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div>
                    <p className="text-xs font-semibold tracking-[0.16em] text-[#cda834]">АДАПТАЦИЯ СОТРУДНИКА</p>
                    <h1 className="mt-1 text-2xl font-bold text-slate-900">{form.title}</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        {form.full_name ? `${form.full_name} · ` : ""}
                        {form.kind_label || ""}
                        {form.plan_date ? ` · до ${formatDateRu(form.plan_date)}` : ""}
                    </p>
                    {form.late_answer ? (
                        <p className="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
                            Ответ будет сохранён как поздний и добавлен в историю версии.
                        </p>
                    ) : null}
                </div>
                <AdaptationQuestionFields
                    questions={form.questions || []}
                    values={values}
                    onChange={(id, value) => setValues((current) => ({ ...current, [id]: value }))}
                    coreHistory={form.core_history || {}}
                    disabled={state === "saving"}
                />
                {message ? <p className="text-sm text-red-700">{message}</p> : null}
                <button disabled={state === "saving"} className="rounded-xl bg-[#0c1835] px-5 py-2.5 text-white disabled:opacity-50">
                    {state === "saving" ? "Отправка…" : "Отправить ответы"}
                </button>
            </form>
        </main>
    );
}
