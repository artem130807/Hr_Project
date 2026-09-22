import { formatRuPhone } from "./phoneSearch";
import { normalizeCallOutcome } from "../data/callOutcomes";

export function mapCallConversation(row) {
    if (!row || typeof row !== "object") return null;
    const caller = row.callerNumber || row.caller_number || "";
    const operator = row.operatorNumber || row.operator_number || "";
    const filename = row.filename || "";
    const name = row.callerName || row.caller_name || formatRuPhone(caller) || "Неизвестный номер";
    const status = normalizeCallOutcome(row.status);
    const description = row.description;
    return {
        id: row.id,
        phone: caller || operator,
        operatorPhone: operator,
        contactName: name,
        vacancy: filename,
        direction: row.direction === "outgoing" ? "outgoing" : "incoming",
        outcome: status,
        startedAt: row.callStartTime || row.call_start_time,
        durationSec: Number(row.duration) || 0,
        recordingName: filename,
        summary: description || (status === "pending" ? "Итог звонка определяется" : ""),
        turns: Array.isArray(row.turns) ? row.turns : [],
        atsStatus: row.atsStatus || row.ats_status || "",
        payload: row.payload,
    };
}

export function mapCallConversations(payload) {
    const list = Array.isArray(payload) ? payload : payload?.items || [];
    return list.map(mapCallConversation).filter(Boolean);
}
