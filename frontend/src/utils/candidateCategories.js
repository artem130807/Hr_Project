/**
 * Candidate category mapping (TZ): UI categories ↔ Candidate.stage / status.
 */

export const CANDIDATE_CATEGORIES = [
    { id: "candidate", label: "Кандидат" },
    { id: "archive", label: "Архив" },
    { id: "blacklist", label: "Черный список" },
    { id: "staff", label: "Штатник" },
];

const STAGE_TO_CATEGORY = {
    "в процессе найма": "candidate",
    "архивирован": "archive",
    "в черном списке": "blacklist",
    "нанят": "staff",
};

const STATUS_TO_CATEGORY = {
    "не подходит": "archive",
    "отказался": "archive",
    "отказ": "archive",
    "уволился": "archive",
    "ВНР": "staff",
};

export function categoryFromCandidate(candidate) {
    if (!candidate) return "candidate";
    const byStatus = STATUS_TO_CATEGORY[candidate.status];
    if (byStatus) return byStatus;
    const byStage = STAGE_TO_CATEGORY[candidate.stage];
    if (byStage) return byStage;
    return "candidate";
}

export function categoryLabel(categoryId) {
    return CANDIDATE_CATEGORIES.find((c) => c.id === categoryId)?.label || categoryId;
}

/** Deadline highlight for planned close dates (TZ: yellow −3d, red overdue). */
export function deadlineHighlight(dateStr, today = new Date()) {
    if (!dateStr) return null;
    const d = new Date(String(dateStr).slice(0, 10) + "T12:00:00");
    if (Number.isNaN(d.getTime())) return null;
    const t = new Date(today);
    t.setHours(12, 0, 0, 0);
    const diffDays = Math.ceil((d - t) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return "overdue";
    if (diffDays <= 3) return "warning";
    return "ok";
}

export function daysBetween(fromIso, to = new Date()) {
    if (!fromIso) return null;
    const from = new Date(fromIso);
    if (Number.isNaN(from.getTime())) return null;
    return Math.max(0, Math.floor((to - from) / (1000 * 60 * 60 * 24)));
}
