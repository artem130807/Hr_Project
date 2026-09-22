import {http} from "../utils/http";

export const getBlackListedCandidates = () => http.get("/candidates/blacklisted")

export const blockCandidate = (candidateId) => http.put(`/candidate/${candidateId}/blacklist`)

export const unblockCandidate = (candidateId) => http.put(`/candidate/${candidateId}/unblacklist`)