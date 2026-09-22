function payloadFor(answers, role) {
    const item = (answers || []).find((a) => a.role === role);
    return item?.payload || {};
}

export function managerSafeReport(row) {
    const hr = payloadFor(row.answers, "hr");
    return {
        employee: row.full_name,
        stage: row.kind_label || row.kind,
        status: row.status_label || row.status,
        risk: row.risk_label || row.risk,
        hr_notes: hr.manager_summary || "Комментарий для руководителя не заполнен.",
        recommendation: hr.hr_recommend,
    };
}

export function internalSlice(row) {
    return {
        employee: row.full_name,
        department: row.department,
        position: row.position,
        stage: row.kind_label || row.kind,
        status: row.status_label || row.status,
        risk: row.risk_label || row.risk,
        outcome: row.outcome,
        answers: row.answers || [],
    };
}

export function probationConclusion(rows) {
    const month2 = (rows || []).filter((r) => r.kind === "month_2");
    const control = (rows || []).filter((r) => r.kind === "control_2m");
    const chosen = month2.length
        ? month2[month2.length - 1]
        : control.length
          ? control[control.length - 1]
          : rows?.[rows.length - 1];
    if (!chosen) return { decision: "insufficient_data", text: "Нет срезов для заключения." };
    const rec = payloadFor(chosen.answers, "hr").hr_recommend;
    const recN = rec == null || rec === "" ? null : Number(rec);
    const risk = chosen.risk || "uncalculated";
    let decision = "attention";
    if (recN != null && recN <= 2) decision = "not_confirmed";
    else if (recN != null && recN >= 4) decision = "confirmed";
    else if (risk === "high") decision = "not_confirmed";
    else if (risk === "low") decision = "confirmed";
    return { decision, risk, outcome: chosen.outcome, stage: chosen.kind_label, text: chosen.outcome };
}

export function buildReports(rows) {
    return {
        internal: (rows || []).map(internalSlice),
        manager_safe: (rows || []).map(managerSafeReport),
        probation: probationConclusion(rows),
    };
}
