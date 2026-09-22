import { http } from "../utils/http";

export const getPublicCandidateDocumentsForm = (token) => http.get(`/public/candidate-documents/${encodeURIComponent(token)}`, { auth: false });
export const openCandidateDocumentsUploadSession = (token, sessionToken = "") =>
    http.post(`/public/candidate-documents/${encodeURIComponent(token)}/upload-sessions`, {
        session_token: sessionToken || null,
    }, { auth: false });
export const uploadCandidateDocumentDraftFile = (token, sessionToken, entry) => {
    const body = new FormData();
    body.append("session_token", sessionToken);
    body.append("kind", entry.kind);
    body.append("file", entry.file, entry.file.name);
    return http.post(`/public/candidate-documents/${encodeURIComponent(token)}/upload-sessions/files`, body, { auth: false });
};
export const deleteCandidateDocumentDraftFile = (token, sessionToken, fileId) =>
    http.del(`/public/candidate-documents/${encodeURIComponent(token)}/upload-sessions/files/${encodeURIComponent(fileId)}`, {
        auth: false,
        headers: { "X-Upload-Session": sessionToken },
    });
export const submitPublicCandidateDocuments = (token, sessionToken) =>
    http.post(`/public/candidate-documents/${encodeURIComponent(token)}/upload-sessions/submit`, {
        session_token: sessionToken,
    }, { auth: false });
export const listCandidateDocuments = () => http.get("/candidate-documents");
export const completeCandidateDocuments = (id) => http.post(`/candidate-documents/${id}/complete`, {});
