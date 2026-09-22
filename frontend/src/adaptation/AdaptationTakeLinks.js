import { useState } from "react";
import { formatDateRu } from "./rules";
import {
    TAKE_ROLE_LABELS,
    adaptationFormAbsoluteUrl,
    copyText,
    employeeTakeLinks,
} from "./takeLinks";

export default function AdaptationTakeLinks({
    links = [],
    employeeId,
    fullName,
    compact = false,
    onCopied,
    onRotate,
}) {
    const [copiedToken, setCopiedToken] = useState("");
    const items = Array.isArray(links) ? links : [];
    const employeeLinks = employeeTakeLinks(items);
    const shown = compact ? employeeLinks : items;

    if (!shown.length) {
        return (
            <p className="text-sm text-slate-500" data-testid="adaptation-take-links-empty">
                Ссылку сотруднику можно получить после постановки на полный маршрут. На контрольном маршруте анкету заполняет HR.
            </p>
        );
    }

    const copyLink = async (item) => {
        const url = item.url || adaptationFormAbsoluteUrl(item.token);
        const ok = await copyText(url);
        if (ok) {
            setCopiedToken(item.token);
            onCopied?.(url, item);
        }
    };

    return (
        <div className="space-y-2" data-testid="adaptation-take-links">
            {fullName || employeeId ? (
                <p className="text-sm text-slate-600">
                    {fullName ? <b className="text-slate-900">{fullName}</b> : null}
                    {employeeId ? <span className="ml-1 text-xs text-slate-400">ID {employeeId}</span> : null}
                </p>
            ) : null}
            {shown.map((item) => {
                const url = item.url || adaptationFormAbsoluteUrl(item.token);
                const label = item.kind_label || item.role_label || TAKE_ROLE_LABELS[item.role] || item.role;
                return (
                    <div
                        key={`${item.role}-${item.token}`}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2.5"
                        data-testid={`take-link-${item.role}-${item.checkpoint_id || item.token}`}
                    >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="min-w-0">
                                <p className="text-sm font-medium text-slate-900">
                                    {label}
                                    {item.role !== "employee" ? ` · ${TAKE_ROLE_LABELS[item.role] || item.role}` : ""}
                                </p>
                                <p className="text-xs text-slate-500">
                                    {item.plan_date ? `план ${formatDateRu(item.plan_date)}` : "персональная ссылка"}
                                    {item.submitted_at ? " · ответы уже отправлены" : ""}
                                </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <a
                                    href={item.url || item.path || adaptationFormAbsoluteUrl(item.token)}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50"
                                >
                                    Открыть
                                </a>
                                <button
                                    type="button"
                                    className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800"
                                    onClick={() => copyLink(item)}
                                >
                                    {copiedToken === item.token ? "Скопировано" : "Копировать ссылку"}
                                </button>
                                {onRotate && !item.submitted_at && !item.locked ? <button type="button" className="rounded-lg border border-amber-300 px-3 py-1.5 text-sm text-amber-800 hover:bg-amber-50" onClick={() => onRotate(item)}>Перевыпустить</button> : null}
                            </div>
                        </div>
                        <p className="mt-1 truncate text-xs text-slate-400" title={url}>{url}</p>
                    </div>
                );
            })}
        </div>
    );
}
