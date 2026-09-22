import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import MainLayout from "../layout/MainLayout";
import { useAlertContext } from "../context/AlertContext";
import { useAuth } from "../context/AuthContext";
import {
    addAdaptationCheckpoint,
    archiveAdaptationEnrollment,
    changeAdaptationManager,
    createAdaptationAction,
    downloadAdaptationDocument,
    downloadAdaptationDocumentsZip,
    finalizeAdaptationEnrollment,
    getAdaptationActions,
    getAdaptationDocuments,
    generateAdaptationDocuments,
    getAdaptationEnrollment,
    getTemporaryAdaptationMatches,
    linkTemporaryAdaptation,
    restartAdaptationEnrollment,
    getAdaptationTakeLinks,
    rotateAdaptationFormToken,
    updateAdaptationRoutingPolicy,
    resolveAdaptationRecipient,
    getAdaptationRoutingDecisions,
    updateAdaptationAction,
} from "../services/adaptationApi";
import AdaptationTakeLinks from "../adaptation/AdaptationTakeLinks";
import { CORE_EMPLOYEE_IDS } from "../adaptation/catalog";
import { formatDateRu, KIND_LABELS, STATUS_LABELS } from "../adaptation/rules";

// This key deduplicates requests; it is not an authentication credential.
const newSeriesKey = () => window.crypto?.randomUUID?.() || `series-${Date.now()}-${Math.random().toString(36).slice(2)}`;

const CORE_LABELS = {
    core_e1: "Комфорт",
    core_e2: "Понятность задач",
    core_e3: "Уверенность",
    core_e4: "Коллеги",
    core_e5: "Поддержка",
};
const MANAGER_CORE_LABELS = {
    core_m1: "Понимание задач", core_m2: "Качество и сроки", core_m3: "Самостоятельность",
    core_m4: "Взаимодействие", core_m5: "Обратная связь", core_m6: "Нагрузка",
};

export default function AdaptationCasePage() {
    const { enrollmentId } = useParams();
    const navigate = useNavigate();
    const { showAlert } = useAlertContext();
    const { user } = useAuth() || {};
    const isHr = ["superadmin", "admin", "manager", "senior_manager", "hr", "owner", "dev", "tech_admin", "director"].includes(user?.role);
    const [data, setData] = useState(null);
    const [actions, setActions] = useState([]);
    const [documents, setDocuments] = useState([]);
    const [frequency, setFrequency] = useState('once');
    const [repeatCount, setRepeatCount] = useState(4);
    const [intervalDays, setIntervalDays] = useState(14);
    const [includeHr, setIncludeHr] = useState(false);
    const [seriesKey, setSeriesKey] = useState(newSeriesKey);
    const [temporaryMatches, setTemporaryMatches] = useState([]);
    const [extraDate, setExtraDate] = useState("");
    const [saving, setSaving] = useState(false);
    const [takeLinks, setTakeLinks] = useState([]);
    const [linksLoading, setLinksLoading] = useState(false);
    const [includeInternalLinks, setIncludeInternalLinks] = useState(false);
    const [routingDecisions, setRoutingDecisions] = useState([]);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const row = await getAdaptationEnrollment(enrollmentId);
                if (!cancelled && row) {
                    setData(row);
                    setTakeLinks(row.take_links || []);
                    if (typeof getAdaptationActions === "function") getAdaptationActions(enrollmentId).then(setActions).catch(() => setActions([]));
                    if (typeof getAdaptationDocuments === "function") getAdaptationDocuments(enrollmentId).then(setDocuments).catch(() => setDocuments([]));
                    if (typeof getAdaptationRoutingDecisions === "function") getAdaptationRoutingDecisions(enrollmentId).then(setRoutingDecisions).catch(() => setRoutingDecisions([]));
                    if (row.temporary_employee_id && !row.employee_id && typeof getTemporaryAdaptationMatches === "function") {
                        getTemporaryAdaptationMatches(row.temporary_employee_id).then(setTemporaryMatches).catch(() => setTemporaryMatches([]));
                    }
                }
            } catch (err) {
                if (!cancelled) showAlert(err.message || "Не удалось загрузить карточку", "error");
            }
        })();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [enrollmentId]);

    const generateTakeLinks = async (includeInternal = includeInternalLinks) => {
        try {
            setLinksLoading(true);
            const payload = await getAdaptationTakeLinks(enrollmentId, includeInternal);
            setTakeLinks(payload?.links || []);
            showAlert("Ссылки для прохождения готовы. Скопируйте нужную и отправьте сотруднику.", "success");
        } catch (error) {
            showAlert(error.message || "Не удалось получить ссылки", "error");
        } finally {
            setLinksLoading(false);
        }
    };

    const rotateTakeLink = async (item) => {
        const reason = window.prompt("Укажите причину перевыпуска ссылки");
        if (!reason?.trim()) return;
        if (!window.confirm("Старая ссылка сразу перестанет работать. Перевыпустить ссылку?")) return;
        try {
            await rotateAdaptationFormToken(item.form_id, { confirmed: true, reason: reason.trim() });
            await generateTakeLinks();
            showAlert("Ссылка перевыпущена, старая ссылка недействительна", "success");
        } catch (error) {
            showAlert(error.message || "Не удалось перевыпустить ссылку", "error");
        }
    };

    const configureRouting = async () => {
        const responsible = window.prompt("ERP ID ответственного HR (можно оставить пустым)", data.responsible_hr_user_id || "");
        if (responsible === null) return;
        const allowPersonal = window.confirm("Разрешить резервное использование личного Telegram сотрудника?");
        try {
            const policy = await updateAdaptationRoutingPolicy(enrollmentId, { responsible_hr_user_id: responsible || null, allow_personal_telegram_fallback: allowPersonal });
            setData((current) => ({ ...current, ...policy }));
            showAlert("Политика получателя сохранена", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const previewRouting = async () => {
        try {
            const decision = await resolveAdaptationRecipient(enrollmentId);
            setRoutingDecisions((rows) => [decision, ...rows]);
            showAlert("Получатель рассчитан. Отправка не выполнялась.", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    if (!data) {
        return (
            <MainLayout>
                <p className="text-slate-500">Загрузка карточки адаптации…</p>
            </MainLayout>
        );
    }

    const addExtra = async (e) => {
        e.preventDefault();
        if (!extraDate) return;
        try {
            setSaving(true);
            await addAdaptationCheckpoint({
                enrollment_id: Number(enrollmentId), plan_date: extraDate, kind: "extra", frequency,
                repeat_count: frequency === 'once' ? 1 : Number(repeatCount),
                interval_days: frequency === 'custom' ? Number(intervalDays) : null,
                series_key: seriesKey, include_hr: includeHr,
            });
            const row = await getAdaptationEnrollment(enrollmentId);
            setData(row);
            setTakeLinks(row.take_links || []);
            setExtraDate("");
            setSeriesKey(newSeriesKey());
            showAlert("Дополнительная точка добавлена", "success");
        } catch (err) {
            showAlert(err.message || String(err), "error");
        } finally {
            setSaving(false);
        }
    };

    const saveBlob = (blob, name) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = name;
        anchor.click();
        URL.revokeObjectURL(url);
    };

    const addAction = async () => {
        const action = window.prompt("Что нужно сделать?");
        if (!action) return;
        const dueDate = window.prompt("Срок (ГГГГ-ММ-ДД), можно оставить пустым", "") || null;
        try {
            const row = await createAdaptationAction(enrollmentId, { action, due_date: dueDate });
            setActions((current) => [row, ...current]);
        } catch (error) { showAlert(error.message, "error"); }
    };

    const completeAction = async (item) => {
        const effect = window.prompt("Фактический результат действия", item.effect || "") || null;
        try {
            const updated = await updateAdaptationAction(item.id, { status: "done", effect });
            setActions((current) => current.map((row) => row.id === item.id ? updated : row));
        } catch (error) { showAlert(error.message, "error"); }
    };

    const finalizeCase = async () => {
        const comment = window.prompt("Итоговый комментарий HR", "") ?? "";
        try {
            await finalizeAdaptationEnrollment(enrollmentId, { outcome: "stable", risk: data.risk || "low", comment, credit_hiring_request: false });
            setData(await getAdaptationEnrollment(enrollmentId));
            showAlert("Кейс завершён", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const archiveCase = async () => {
        const reason = window.prompt("Причина архивирования");
        if (!reason) return;
        try {
            await archiveAdaptationEnrollment(enrollmentId, { reason });
            showAlert("Кейс перенесён в архив, напоминания отменены", "success");
            navigate("/tests/adaptation");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const changeManager = async () => {
        const managerUserId = window.prompt("ERP ID нового руководителя", data.manager_user_id || "");
        if (!managerUserId) return;
        const managerName = window.prompt("ФИО руководителя", data.manager_name || "") || null;
        try {
            await changeAdaptationManager(enrollmentId, { manager_user_id: managerUserId, manager_name: managerName });
            setData(await getAdaptationEnrollment(enrollmentId));
            showAlert("Руководитель и персональные ссылки обновлены", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const linkMatch = async (employeeId) => {
        try {
            await linkTemporaryAdaptation(data.temporary_employee_id, { employee_id: employeeId });
            setData(await getAdaptationEnrollment(enrollmentId));
            setTemporaryMatches([]);
            showAlert("Временная карточка связана с сотрудником без потери истории", "success");
        } catch (error) { showAlert(error.message, "error"); }
    };

    const restartAfterTransfer = async () => {
        const startDate = window.prompt("Дата начала новой адаптации после перевода (ГГГГ-ММ-ДД)");
        if (!startDate) return;
        const reason = window.prompt("Основание: новая должность/перевод");
        if (!reason) return;
        try {
            const created = await restartAdaptationEnrollment(enrollmentId, { start_date: startDate, reason, route: "full" });
            showAlert("Создан новый связанный кейс адаптации", "success");
            navigate(`/tests/adaptation/case/${created.id}`);
        } catch (error) { showAlert(error.message, "error"); }
    };

    return (
        <MainLayout className="flex flex-col h-full overflow-y-auto">
            <button type="button" className="text-sm text-slate-500 mb-4" onClick={() => navigate("/tests/adaptation")}>
                ← К списку адаптации
            </button>
            <div className="mb-6">
                <p className="text-xs font-semibold tracking-[0.16em] text-slate-400">ТЕСТЫ / АДАПТАЦИЯ</p>
                <h1 className="text-2xl font-bold" data-testid="adaptation-case-title">
                    {data.full_name}
                </h1>
                <p className="text-sm text-slate-500">
                    {data.position} · {data.department} · принят {formatDateRu(data.date_hired)}
                </p>
                <p className="text-sm text-slate-500">Маршрут: {data.route === "control" ? "контрольный" : "полный"} · Руководитель: {data.manager_name || "не назначен"}</p>
                {data.archived ? <p className="mt-2 text-sm text-amber-700">Кейс находится в архиве{data.archive_reason ? `: ${data.archive_reason}` : ""}</p> : null}
                {isHr && !data.archived ? <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" onClick={() => generateTakeLinks()} className="text-sm px-3 py-1.5 rounded-lg border" disabled={linksLoading}>
                        {linksLoading ? "Готовим ссылку…" : "Сгенерировать ссылку сотруднику"}
                    </button>
                    <button type="button" onClick={changeManager} className="text-sm px-3 py-1.5 rounded-lg border">Сменить руководителя</button>
                    {data.employee_id ? <button type="button" onClick={restartAfterTransfer} className="text-sm px-3 py-1.5 rounded-lg border">Новая адаптация после перевода</button> : null}
                    <button type="button" onClick={finalizeCase} className="text-sm px-3 py-1.5 rounded-lg border">Завершить кейс</button>
                    <button type="button" onClick={archiveCase} className="text-sm px-3 py-1.5 rounded-lg border text-red-700">В архив</button>
                </div> : null}
                {isHr && temporaryMatches.length ? <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3"><b className="text-sm">Найдены возможные совпадения в ERP</b>{temporaryMatches.map((match) => <div key={match.employee_id} className="mt-2 flex items-center justify-between gap-3 text-sm"><span>{match.full_name} · {match.position} · совпадение {match.score}%</span><button type="button" onClick={() => linkMatch(match.employee_id)} className="underline">Связать</button></div>)}</div> : null}
            </div>

            {isHr ? (
                <section className="bg-white rounded-2xl border border-slate-200/60 p-5 mb-4">
                    <h2 className="font-medium mb-3">Ссылки для прохождения анкеты</h2>
                    <p className="mb-3 text-sm text-slate-500">
                        Откройте форму, чтобы посмотреть вопросы, или скопируйте ссылку и отправьте её сотруднику. Ответы сохраняются в этом кейсе.
                    </p>
                    <label className="mb-3 flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={includeInternalLinks} onChange={(event) => { const next = event.target.checked; setIncludeInternalLinks(next); generateTakeLinks(next); }} />Показать формы руководителя и HR</label>
                    <AdaptationTakeLinks
                        links={takeLinks}
                        employeeId={data.employee_id}
                        fullName={data.full_name}
                        onRotate={rotateTakeLink}
                    />
                </section>
            ) : null}

            {isHr ? <section className="bg-white rounded-2xl border border-slate-200/60 p-5 mb-4">
                <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-medium">Политика контакта</h2><p className="text-sm text-slate-500">Расчёт получателя без отправки уведомления.</p></div><div className="flex gap-2"><button type="button" className="rounded-lg border px-3 py-2 text-sm" onClick={configureRouting}>Настроить</button><button type="button" className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white" onClick={previewRouting}>Проверить маршрут</button></div></div>
                <p className="mt-3 text-sm">Ответственный HR: {data.responsible_hr_name || data.responsible_hr_user_id || "роль HR"} · личный Telegram: {data.allow_personal_telegram_fallback ? "разрешён как резервный" : "не используется"}</p>
                <div className="mt-3 space-y-1 text-xs text-slate-500">{routingDecisions.slice(0, 5).map((item) => <p key={item.id}>#{item.id}: {item.recipient_type} · {item.reason} · {item.status}</p>)}</div>
            </section> : null}

            <section className="bg-white rounded-2xl border border-slate-200/60 p-5 mb-4">
                <h2 className="font-medium mb-3">Лента этапов</h2>
                <ol className="space-y-2" data-testid="adaptation-timeline">
                    {(data.checkpoints || []).map((cp) => (
                        <li key={cp.id} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2">
                            <div>
                                <b className="block text-sm">{cp.kind_label || KIND_LABELS[cp.kind]}</b>
                                <small className="text-slate-500">
                                    план {formatDateRu(cp.plan_date)} · {cp.status_label || STATUS_LABELS[cp.status]}
                                    {cp.recurrence_rule ? ` · ${cp.recurrence_rule.frequency === "weekly" ? "еженедельно" : cp.recurrence_rule.frequency === "monthly" ? "ежемесячно" : cp.recurrence_rule.frequency === "custom" ? `каждые ${cp.recurrence_rule.interval_days} дн.` : "однократно"} (${cp.recurrence_rule.count})` : ""}
                                    {cp.talk_hr ? " · запрос разговора с HR" : ""}
                                </small>
                            </div>
                            <button
                                type="button"
                                className="text-sm px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"
                                onClick={() => navigate(`/tests/adaptation/${cp.id}`)}
                            >
                                Открыть
                            </button>
                        </li>
                    ))}
                </ol>
            </section>

            {Object.values(data.manager_core_series || {}).some((series) => series.length) ? <section className="bg-white rounded-2xl border border-slate-200/60 p-5 mb-4">
                <h2 className="font-medium mb-3">Отдельная динамика оценок руководителя</h2>
                <div className="grid gap-3 md:grid-cols-6">{Object.entries(MANAGER_CORE_LABELS).map(([qid, label]) => {
                    const series = data.manager_core_series?.[qid] || [];
                    return <div key={qid} className="border rounded-xl p-3"><p className="text-xs text-slate-500 mb-2">{label}</p><div className="flex items-end gap-1 h-16">{series.map((point) => <div key={`${point.kind}-${point.plan_date}`} title={`${point.kind}: ${point.value}`} className="flex-1 bg-sky-700 rounded-t" style={{ height: `${(Number(point.value) / 5) * 100}%` }} />)}</div></div>;
                })}</div>
            </section> : null}

            <section className="bg-white rounded-2xl border border-slate-200/60 p-5 mb-4">
                <div className="flex justify-between gap-3 mb-3"><h2 className="font-medium">План действий HR</h2>{isHr ? <button type="button" onClick={addAction} className="text-sm underline">Добавить</button> : null}</div>
                {actions.length ? actions.map((item) => <div key={item.id} className="border-t py-2 flex justify-between gap-3 text-sm"><span>{item.action}{item.due_date ? ` · до ${formatDateRu(item.due_date)}` : ""}<small className="block text-slate-500">{item.status}{item.effect ? ` · ${item.effect}` : ""}</small></span>{isHr && item.status !== "done" ? <button type="button" onClick={() => completeAction(item)} className="underline">Выполнено</button> : null}</div>) : <p className="text-sm text-slate-400">Действия пока не запланированы.</p>}
            </section>

            <section className="bg-white rounded-2xl border border-slate-200/60 p-5 mb-4">
                <div className="flex justify-between gap-3 mb-3"><h2 className="font-medium">Документы и версии</h2>{isHr && documents.length ? <button type="button" onClick={async () => saveBlob(await downloadAdaptationDocumentsZip(enrollmentId), `adaptation_${enrollmentId}.zip`)} className="text-sm underline">Скачать ZIP</button> : null}</div>
                {isHr ? <div className="flex flex-wrap gap-2 mb-3">{(data.checkpoints || []).filter(stage => stage.kind !== 'control_2m').map(stage => <button key={stage.id} className="border rounded-lg px-3 py-2 text-sm" onClick={async () => {
                    try {
                        await generateAdaptationDocuments(stage.id, { formats: ['docx', 'pdf'], final: stage.status === 'completed' });
                        setDocuments(await getAdaptationDocuments(enrollmentId));
                        showAlert('Документы сформированы', 'success');
                    } catch (error) { showAlert(error.message || 'Не удалось сформировать документы', 'error'); }
                }}>Сформировать: {stage.kind_label || KIND_LABELS[stage.kind]}</button>)}</div> : null}
                {documents.length ? documents.map((item) => <button type="button" key={item.id} onClick={async () => saveBlob(await downloadAdaptationDocument(item.id), item.file_name)} className="block text-left text-sm py-1 underline">{item.file_name} · v{item.version}{item.is_final ? " · итоговый" : ""}</button>) : <p className="text-sm text-slate-400">Документы формируются на странице этапа.</p>}
            </section>

            <section className="bg-white rounded-2xl border border-slate-200/60 p-5 mb-4" data-testid="core-series">
                <h2 className="font-medium mb-3">Динамика 5 базовых шкал сотрудника</h2>
                <div className="grid gap-3 md:grid-cols-5">
                    {CORE_EMPLOYEE_IDS.map((qid) => {
                        const series = data.core_series?.[qid] || [];
                        return (
                            <div key={qid} className="border border-slate-100 rounded-xl p-3">
                                <p className="text-xs text-slate-500 mb-2">{CORE_LABELS[qid]}</p>
                                {series.length === 0 ? (
                                    <p className="text-xs text-slate-400">нет оценок</p>
                                ) : (
                                    <div className="flex items-end gap-1 h-16">
                                        {series.map((point) => (
                                            <div
                                                key={`${point.kind}-${point.plan_date}`}
                                                title={`${point.kind}: ${point.value}`}
                                                className="flex-1 bg-slate-800 rounded-t"
                                                style={{ height: `${(Number(point.value) / 5) * 100}%` }}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </section>

            <form onSubmit={addExtra} className="bg-white rounded-2xl border border-slate-200/60 p-5 flex flex-wrap items-end gap-3">
                <label className="text-sm">Повторение<select className="block border rounded-xl p-2" value={frequency} onChange={e => { setFrequency(e.target.value); setSeriesKey(newSeriesKey()); }}>
                    <option value="once">Однократно</option><option value="weekly">Еженедельно</option><option value="monthly">Ежемесячно</option><option value="custom">Свой интервал</option>
                </select></label>
                {frequency !== 'once' ? <label className="text-sm">Количество точек<input type="number" min="1" max="52" value={repeatCount} onChange={e => { setRepeatCount(e.target.value); setSeriesKey(newSeriesKey()); }} className="block border rounded-xl p-2" /></label> : null}
                {frequency === 'custom' ? <label className="text-sm">Интервал, дней<input type="number" min="1" max="365" value={intervalDays} onChange={e => { setIntervalDays(e.target.value); setSeriesKey(newSeriesKey()); }} className="block border rounded-xl p-2" /></label> : null}
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={includeHr} onChange={e => { setIncludeHr(e.target.checked); setSeriesKey(newSeriesKey()); }} />Добавить комментарий HR</label>
                <label className="text-sm">
                    <span className="text-slate-500">Дополнительная точка</span>
                    <input
                        type="date"
                        className="mt-1 block border rounded-xl px-3 py-2"
                        value={extraDate}
                        onChange={(e) => { setExtraDate(e.target.value); setSeriesKey(newSeriesKey()); }}
                    />
                </label>
                <button
                    type="submit"
                    disabled={saving || !extraDate}
                    className="bg-slate-900 text-white px-4 py-2 rounded-xl text-sm disabled:opacity-50"
                >
                    Добавить опрос
                </button>
                <p className="text-xs text-slate-500">Для сотрудника заголовок будет «Адаптационный опрос». Если дата выпадает на выходной, план сдвинется на ближайший рабочий день.</p>
            </form>
        </MainLayout>
    );
}
