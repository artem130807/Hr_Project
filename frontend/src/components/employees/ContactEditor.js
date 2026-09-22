import { useState } from "react";

const EMPTY = { contact_type: "telegram", value: "", usage_type: "work_personal", label: "", priority: 100, is_primary: false, is_active: true, allow_adaptation: false, telegram_chat_id: "", verified: false };
const TYPE_LABEL = { telegram: "Telegram", phone: "Телефон", email: "Email" };
const USAGE_LABEL = { personal: "Личный", work_personal: "Рабочий персональный", shared: "Общий" };

export default function ContactEditor({ contacts = [], departmentMode = false, readOnly = false, onCreate, onUpdate, onDeactivate }) {
    const [form, setForm] = useState({ ...EMPTY, usage_type: departmentMode ? "shared" : "work_personal" });
    const submit = async (event) => {
        event.preventDefault();
        const { verified, ...payload } = form;
        await onCreate({ ...payload, label: form.label || null, telegram_chat_id: form.contact_type === "telegram" ? (form.telegram_chat_id || null) : null, verified_at: form.contact_type === "telegram" && verified ? new Date().toISOString() : null });
        setForm({ ...EMPTY, usage_type: departmentMode ? "shared" : "work_personal" });
    };
    return <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold">Контакты</h2>
        <p className="mt-1 text-sm text-slate-500">Можно хранить несколько контактов. Общие контакты закрепляются только за отделом.</p>
        <div className="mt-4 space-y-2" data-testid="contact-list">
            {contacts.map((item) => <div key={item.id} className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 ${item.is_active ? "border-slate-200" : "border-slate-100 opacity-50"}`}>
                <div><b>{TYPE_LABEL[item.contact_type] || item.contact_type}: {item.value}</b><p className="text-xs text-slate-500">{USAGE_LABEL[item.usage_type]}{item.is_primary ? " · основной" : ""}{item.allow_adaptation ? " · разрешён для адаптации" : ""}{item.contact_type === "telegram" ? (item.verified_at ? " · подтверждён" : " · не подтверждён") : ""}</p></div>
                {!readOnly ? <div className="flex gap-2">
                    {!departmentMode && item.is_active && !item.is_primary ? <button type="button" className="text-sm underline" onClick={() => onUpdate(item.id, { is_primary: true })}>Сделать основным</button> : null}
                    {item.is_active ? <button type="button" className="text-sm text-red-700" onClick={() => onDeactivate(item.id)}>Отключить</button> : null}
                </div> : null}
            </div>)}
            {!contacts.length ? <p className="text-sm text-slate-400">Контакты пока не добавлены.</p> : null}
        </div>
        {!readOnly ? <form onSubmit={submit} className="mt-5 grid gap-3 md:grid-cols-2" data-testid="contact-form">
            <select className="rounded-xl border px-3 py-2" value={form.contact_type} onChange={(e) => setForm({ ...form, contact_type: e.target.value, allow_adaptation: false, telegram_chat_id: "", verified: false })}><option value="telegram">Telegram</option><option value="phone">Телефон</option><option value="email">Email</option></select>
            <input className="rounded-xl border px-3 py-2" required placeholder="Значение контакта" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
            {!departmentMode ? <select className="rounded-xl border px-3 py-2" value={form.usage_type} onChange={(e) => setForm({ ...form, usage_type: e.target.value })}><option value="work_personal">Рабочий персональный</option><option value="personal">Личный</option></select> : <input type="hidden" value="shared" />}
            <input className="rounded-xl border px-3 py-2" placeholder="Название / назначение" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
            {form.contact_type === "telegram" ? <input className="rounded-xl border px-3 py-2" placeholder="Telegram chat ID (после подтверждения)" value={form.telegram_chat_id} onChange={(e) => setForm({ ...form, telegram_chat_id: e.target.value })} /> : null}
            {form.contact_type === "telegram" ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.verified} onChange={(e) => setForm({ ...form, verified: e.target.checked })} />Контакт подтверждён</label> : null}
            {!departmentMode && form.contact_type === "telegram" ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.allow_adaptation} onChange={(e) => setForm({ ...form, allow_adaptation: e.target.checked })} />Разрешить использовать для адаптации</label> : null}
            {!departmentMode ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_primary} onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} />Основной</label> : null}
            <button className="rounded-xl bg-slate-900 px-4 py-2 text-white md:col-span-2">Добавить контакт</button>
        </form> : null}
    </section>;
}
