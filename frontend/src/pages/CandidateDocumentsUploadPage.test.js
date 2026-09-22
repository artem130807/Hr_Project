/** @jest-environment jsdom */
import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CandidateDocumentsUploadPage from "./CandidateDocumentsUploadPage";
import {
    deleteCandidateDocumentDraftFile, getPublicCandidateDocumentsForm,
    openCandidateDocumentsUploadSession, submitPublicCandidateDocuments,
    uploadCandidateDocumentDraftFile,
} from "../services/candidateDocumentsApi";
import { CANDIDATE_DOCUMENT_SESSION_KEY } from "../utils/candidateDocumentsSession";

jest.mock("react-router-dom", () => ({ useParams: () => ({ token: "invite-1" }) }), { virtual: true });
jest.mock("../services/candidateDocumentsApi", () => ({
    getPublicCandidateDocumentsForm: jest.fn(),
    openCandidateDocumentsUploadSession: jest.fn(),
    uploadCandidateDocumentDraftFile: jest.fn(),
    deleteCandidateDocumentDraftFile: jest.fn(),
    submitPublicCandidateDocuments: jest.fn(),
}));

beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    getPublicCandidateDocumentsForm.mockResolvedValue({ candidate: { full_name: "Тестовый кандидат" } });
    openCandidateDocumentsUploadSession.mockResolvedValue({ session_token: "opaque-token", files: [] });
    uploadCandidateDocumentDraftFile.mockResolvedValue({
        file_id: "file-1", kind: "passport", filename: "passport.pdf", size: 12,
    });
    submitPublicCandidateDocuments.mockResolvedValue({ id: 10 });
    deleteCandidateDocumentDraftFile.mockResolvedValue({ deleted: true });
    jest.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => jest.restoreAllMocks());

test("restores server-side draft after reopening, stores only session token", async () => {
    localStorage.setItem(CANDIDATE_DOCUMENT_SESSION_KEY, "opaque-token");
    openCandidateDocumentsUploadSession.mockResolvedValue({
        files: [{ file_id: "file-1", kind: "passport", filename: "passport.pdf", size: 12 }],
    });
    render(<CandidateDocumentsUploadPage />);
    expect(await screen.findByText(/passport.pdf/)).toBeInTheDocument();
    expect(openCandidateDocumentsUploadSession).toHaveBeenCalledWith("invite-1", "opaque-token");
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index))).toEqual([CANDIDATE_DOCUMENT_SESSION_KEY]);
    fireEvent.click(screen.getByRole("button", { name: "Отправить пакет документов" }));
    await waitFor(() => expect(submitPublicCandidateDocuments).toHaveBeenCalledWith("invite-1", "opaque-token"));
    expect(localStorage.length).toBe(0);
});

test("uploads file immediately without saving its bytes in browser storage", async () => {
    render(<CandidateDocumentsUploadPage />);
    expect(await screen.findByText(/Тестовый кандидат/)).toBeInTheDocument();
    const input = document.querySelector('input[type="file"]');
    const pdf = new File(["%PDF-document"], "passport.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [pdf] } });
    await waitFor(() => expect(uploadCandidateDocumentDraftFile).toHaveBeenCalledWith(
        "invite-1", "opaque-token", { kind: "passport", file: pdf }
    ));
    expect(await screen.findByText(/passport.pdf/)).toBeInTheDocument();
    expect(localStorage.getItem(CANDIDATE_DOCUMENT_SESSION_KEY)).toBe("opaque-token");
});
