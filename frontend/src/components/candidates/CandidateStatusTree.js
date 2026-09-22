import { flattenStatusTree, CANDIDATE_STATUS_TREE, statusLabel } from "../../utils/candidateStatuses";

/**
 * Hierarchical status picker (Avito/Notion-like tree).
 */
export default function CandidateStatusTree({
    currentStatus,
    onSelect,
    disabled = false,
    statusesFromApi = null,
    allowedTransitions = null,
}) {
    const allowed = new Set(
        (Array.isArray(statusesFromApi) ? statusesFromApi : [])
            .map((s) => String(s.code ?? s.name ?? s.status ?? s).trim())
            .filter(Boolean)
    );
    const rows = flattenStatusTree(CANDIDATE_STATUS_TREE).filter(
        (row) => allowed.size === 0 || allowed.has(row.value)
    );
    const cur = String(currentStatus ?? "").trim();

    return (
        <div
            className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 max-h-[420px] overflow-y-auto"
            data-testid="candidate-status-tree"
        >
            <ul className="space-y-0.5 text-sm">
                {rows.map((row) => {
                    const active = cur === row.value;
                    const transitionAllowed = active || !Array.isArray(allowedTransitions) || allowedTransitions.includes(row.value);
                    return (
                        <li key={row.value} style={{ paddingLeft: row.depth * 16 }}>
                            <button
                                type="button"
                                disabled={disabled || !transitionAllowed}
                                onClick={() => onSelect?.(row.value)}
                                className={`w-full text-left px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-2 ${
                                    active
                                        ? "bg-slate-900 text-white"
                                        : "hover:bg-white text-slate-700"
                                } disabled:opacity-50`}
                                title={transitionAllowed ? statusLabel(row.value) : "Недоступно на текущем этапе"}
                            >
                                <span
                                    className={`shrink-0 w-3 text-center text-[10px] ${
                                        active ? "text-slate-300" : "text-slate-400"
                                    }`}
                                >
                                    {row.hasChildren ? "▾" : "•"}
                                </span>
                                <span className="truncate">{statusLabel(row.value)}</span>
                            </button>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}
