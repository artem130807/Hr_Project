export const CANDIDATE_DOCUMENT_SESSION_KEY = "candidate-documents-upload-session";

export function readCandidateDocumentSession(storage = typeof window !== "undefined" ? window.localStorage : null) {
    try {
        const token = storage?.getItem(CANDIDATE_DOCUMENT_SESSION_KEY);
        return typeof token === "string" && token.trim() ? token.trim() : "";
    } catch {
        return "";
    }
}

export function saveCandidateDocumentSession(token, storage = typeof window !== "undefined" ? window.localStorage : null) {
    try {
        if (!token || !storage) return false;
        storage.setItem(CANDIDATE_DOCUMENT_SESSION_KEY, String(token));
        return true;
    } catch {
        return false;
    }
}

export function clearCandidateDocumentSession(storage = typeof window !== "undefined" ? window.localStorage : null) {
    try {
        storage?.removeItem(CANDIDATE_DOCUMENT_SESSION_KEY);
    } catch {
        // Storage is optional; the active tab still owns the in-memory token.
    }
}
