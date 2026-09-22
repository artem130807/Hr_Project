import { CANDIDATE_DOCUMENT_TYPES } from "../config/candidateDocumentTypes";

export const MAX_CANDIDATE_DOCUMENT_FILES = 20;
export const MAX_CANDIDATE_DOCUMENT_DRAFT_BYTES = 3 * 1024 * 1024;
export const CANDIDATE_DOCUMENT_DRAFT_CONTENT_TYPES = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
]);

const ALLOWED_KINDS = new Set(CANDIDATE_DOCUMENT_TYPES.map((item) => item.value));

export function parseCandidateDocumentsDraft(value) {
    if (!value) return [];
    try {
        const parsed = JSON.parse(value);
        if (!Array.isArray(parsed)) return [];
        return parsed.filter((item) => (
            item
            && typeof item.id === "string"
            && ALLOWED_KINDS.has(item.kind)
            && typeof item.filename === "string"
            && CANDIDATE_DOCUMENT_DRAFT_CONTENT_TYPES.has(item.contentType)
            && Number.isFinite(Number(item.size))
            && Number(item.size) > 0
            && typeof item.dataUrl === "string"
            && item.dataUrl.startsWith(`data:${item.contentType};base64,`)
        )).slice(0, MAX_CANDIDATE_DOCUMENT_FILES);
    } catch {
        return [];
    }
}
