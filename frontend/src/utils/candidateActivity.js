const EXPERIENCE_LABELS = {
    должность: "position",
    компания: "company",
    отрасль: "industry",
    регион: "region",
    период: "period",
    описание: "description",
};

const GENERIC_STATUS_COMMENTS = new Set([
    "status update",
    "archive",
    "hire",
    "unblacklist → archive",
    "смена статуса",
    "переведён в архив",
    "добавлен в чёрный список",
    "оформлен на работу",
    "убран из чёрного списка, переведён в архив",
]);

export function formatRuDateTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

export function actorLabel(name, fallback = "Система") {
    const trimmed = String(name || "").trim();
    return trimmed || fallback;
}

export function parseWorkExperienceBlock(raw) {
    const text = String(raw || "").trim();
    if (!text) return null;

    const fields = {};
    const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    let matchedLabeled = false;

    for (const line of lines) {
        const m = line.match(/^([^:]{2,24}):\s*(.+)$/);
        if (!m) continue;
        const key = EXPERIENCE_LABELS[m[1].trim().toLowerCase()];
        if (!key) continue;
        fields[key] = m[2].trim();
        matchedLabeled = true;
    }

    if (matchedLabeled) {
        return {
            title: fields.position || fields.company || "Опыт работы",
            company: fields.company || "",
            period: fields.period || "",
            industry: fields.industry || "",
            region: fields.region || "",
            description: fields.description || "",
        };
    }

    return {
        title: lines[0] || text,
        company: "",
        period: "",
        industry: "",
        region: "",
        description: lines.slice(1).join("\n"),
    };
}

export function parseWorkExperienceList(value) {
    if (value == null || value === "") return [];
    const items = Array.isArray(value) ? value : [value];
    return items.map(parseWorkExperienceBlock).filter(Boolean);
}

function quote(value) {
    return `«${value}»`;
}

function isGenericComment(comment) {
    return GENERIC_STATUS_COMMENTS.has(String(comment || "").trim().toLowerCase());
}

export function describeStatusEvent(step) {
    const who = actorLabel(step.actor_name);
    const fromStatus = step.from_status;
    const toStatus = step.to_status;
    const fromStage = step.from_stage;
    const toStage = step.to_stage;
    const comment = String(step.comment || "").trim();

    if (toStatus && fromStatus && toStatus !== fromStatus) {
        return `${who} сменил(а) статус с ${quote(fromStatus)} на ${quote(toStatus)}`;
    }
    if (toStatus && !fromStatus) {
        return `${who} установил(а) статус ${quote(toStatus)}`;
    }
    if (toStage && fromStage && toStage !== fromStage) {
        return `${who} перевёл(а) карточку: ${quote(fromStage)} → ${quote(toStage)}`;
    }
    if (toStage && !fromStage) {
        return `${who} установил(а) этап ${quote(toStage)}`;
    }
    if (comment && !isGenericComment(comment)) {
        return `${who}: ${comment}`;
    }
    return `${who} обновил(а) карточку кандидата`;
}

export function statusEventDetail(step) {
    const comment = String(step.comment || "").trim();
    if (!comment || isGenericComment(comment)) return "";
    const title = describeStatusEvent(step);
    if (title.endsWith(comment) || title.includes(comment)) return "";
    return comment;
}

export function mergeCandidateTimeline({ history = [], comments = [], approvals = [] } = {}) {
    const events = [];

    for (const step of history) {
        events.push({
            id: `status-${step.id}`,
            type: "status",
            at: step.created_at,
            actor: actorLabel(step.actor_name),
            title: describeStatusEvent(step),
            detail: statusEventDetail(step),
            raw: step,
        });
    }

    for (const item of comments) {
        events.push({
            id: `comment-${item.id}`,
            type: "comment",
            at: item.created_at,
            actor: actorLabel(item.author_name, "Сотрудник"),
            title: `${actorLabel(item.author_name, "Сотрудник")} оставил(а) комментарий`,
            detail: item.body || "",
            raw: item,
        });
    }

    for (const item of approvals) {
        const who = actorLabel(item.approver_name, item.approver_id ? `Сотрудник #${item.approver_id}` : "Сотрудник");
        events.push({
            id: `approval-${item.id}`,
            type: "approval",
            at: item.created_at,
            actor: who,
            title: `${who} — ${item.new_status || "согласование"}`,
            detail: item.comments || "",
            raw: item,
        });
    }

    events.sort((a, b) => {
        const ta = a.at ? new Date(a.at).getTime() : 0;
        const tb = b.at ? new Date(b.at).getTime() : 0;
        return tb - ta;
    });
    return events;
}
