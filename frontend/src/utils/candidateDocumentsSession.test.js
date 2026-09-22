/** @jest-environment jsdom */
import {
    CANDIDATE_DOCUMENT_SESSION_KEY, clearCandidateDocumentSession,
    readCandidateDocumentSession, saveCandidateDocumentSession,
} from "./candidateDocumentsSession";

test("stores only the opaque upload-session token", () => {
    const storage = new Map();
    const adapter = {
        getItem: (key) => storage.get(key) || null,
        setItem: (key, value) => storage.set(key, value),
        removeItem: (key) => storage.delete(key),
    };
    expect(saveCandidateDocumentSession("random-secret", adapter)).toBe(true);
    expect([...storage.entries()]).toEqual([[CANDIDATE_DOCUMENT_SESSION_KEY, "random-secret"]]);
    expect(readCandidateDocumentSession(adapter)).toBe("random-secret");
    clearCandidateDocumentSession(adapter);
    expect(readCandidateDocumentSession(adapter)).toBe("");
});

test("storage failures do not break the upload page", () => {
    const blocked = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("full"); }, removeItem: () => { throw new Error("blocked"); } };
    expect(readCandidateDocumentSession(blocked)).toBe("");
    expect(saveCandidateDocumentSession("secret", blocked)).toBe(false);
    expect(() => clearCandidateDocumentSession(blocked)).not.toThrow();
});
