/** @jest-environment jsdom */
import {
    completeCandidateDocuments, deleteCandidateDocumentDraftFile, getPublicCandidateDocumentsForm,
    listCandidateDocuments, openCandidateDocumentsUploadSession, submitPublicCandidateDocuments,
    uploadCandidateDocumentDraftFile,
} from "./candidateDocumentsApi";
import { http } from "../utils/http";

jest.mock("../utils/http", () => ({ http: { get: jest.fn(), post: jest.fn(), del: jest.fn() } }));

describe("candidateDocumentsApi", () => {
    beforeEach(() => jest.clearAllMocks());

    it("uses public endpoints without authentication", async () => {
        http.get.mockResolvedValue({ candidate: { id: 1 } });
        await getPublicCandidateDocumentsForm("a/b");
        expect(http.get).toHaveBeenCalledWith("/public/candidate-documents/a%2Fb", { auth: false });
    });

    it("opens, uploads, restores and submits a server-side draft", async () => {
        http.post.mockResolvedValue({ id: 3 });
        const file = new File(["x"], "passport.jpg", { type: "image/jpeg" });
        await openCandidateDocumentsUploadSession("token", "session-secret");
        expect(http.post).toHaveBeenLastCalledWith(
            "/public/candidate-documents/token/upload-sessions",
            { session_token: "session-secret" },
            { auth: false },
        );
        await uploadCandidateDocumentDraftFile("token", "session-secret", { kind: "passport", file });
        const body = http.post.mock.calls[1][1];
        expect(body).toBeInstanceOf(FormData);
        expect(body.get("session_token")).toBe("session-secret");
        expect(body.get("kind")).toBe("passport");
        await deleteCandidateDocumentDraftFile("token", "session-secret", "file-id");
        expect(http.del).toHaveBeenCalledWith(
            "/public/candidate-documents/token/upload-sessions/files/file-id",
            { auth: false, headers: { "X-Upload-Session": "session-secret" } },
        );
        await submitPublicCandidateDocuments("token", "session-secret");
        expect(http.post).toHaveBeenLastCalledWith(
            "/public/candidate-documents/token/upload-sessions/submit",
            { session_token: "session-secret" },
            { auth: false },
        );
    });

    it("exposes HR actions", async () => {
        http.post.mockResolvedValue({ id: 3 });
        await listCandidateDocuments();
        expect(http.get).toHaveBeenCalledWith("/candidate-documents");
        await completeCandidateDocuments(3);
        expect(http.post).toHaveBeenCalledWith("/candidate-documents/3/complete", {});
    });
});
