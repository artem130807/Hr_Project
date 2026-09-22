import { flattenStatusTree } from "./candidateStatuses";

/**
 * Build funnel rows in hierarchy order for analytics UI.
 * @param {Record<string, number>|null|undefined} stats
 */
export function buildCandidateFunnelRows(stats) {
    const map = stats && typeof stats === "object" ? stats : {};
    return flattenStatusTree().map((row) => ({
        name: row.value,
        count: Number(map[row.value] ?? 0) || 0,
        depth: row.depth,
        hasChildren: row.hasChildren,
    }));
}

export function totalFunnelCount(rows) {
    return (rows || []).reduce((sum, row) => sum + (Number(row.count) || 0), 0);
}
