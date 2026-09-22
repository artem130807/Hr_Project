import { http } from "../utils/http";
import { relationVacancyName } from "../utils/candidateMapper";

const normalizeStatusForBackendValue = (status) => {
    if (status == null) return status;
    const s = typeof status === "object" ? (status.code ?? status.name ?? status.id) : status;
    const val = String(s).trim();
    const map = {
        Архив: "отказ",
        "Переведен в архив": "отказ",
        "Черный список": "не подходит",
        "Чёрный список": "не подходит",
        Нанят: "ВНР",
        "Отказ. Переведен в архив": "отказ",
        "Отказ. В черном списке": "не подходит",
        "Отказался от оффера. В архиве.": "отказался",
    };
    return map[val] || val;
};

const normalizeCandidateStatuses = (payload) => {
    const arr = payload?.items || [];

    return arr.map((s, i) => ({
        id: i + 1,
        code: s.status,
        name: s.label || s.status,
        stage: s.stage,
        state: s.state,
        nextAction: s.next_action,
        allowedTransitions: Array.isArray(s.allowed_transitions) ? s.allowed_transitions : undefined,
    }));
};

export const getCandidatesStatuses = async () => {
    const raw = await http.get("/dict/status");
    return normalizeCandidateStatuses(raw);
};

export const getCandidates = (
  status = null,
  search = null,
  role_id = null,
  vacancy_id = null,
  is_perfect_candidate = undefined,
  page = 0,
  per_page = 20,
  category = null,
  opts = {}
) => {
  const params = new URLSearchParams();
  if (status) {
    const raw = typeof status === "object" ? (status.code ?? status.id ?? status.name) : status;
    const normalized = normalizeStatusForBackendValue(raw);
    if (normalized != null && String(normalized).trim()) {
      params.append("status", String(normalized).trim());
    }
  }
  if (role_id) {
    const val = typeof role_id === 'object' ? (role_id.id ?? role_id.code ?? role_id.value) : role_id;
    if (val != null && String(val).trim()) params.append('role_id', String(val).trim());
  }
  const vacancyIds = Array.isArray(vacancy_id)
    ? vacancy_id
    : vacancy_id != null && String(vacancy_id).trim()
      ? [vacancy_id]
      : [];
  for (const raw of vacancyIds) {
    const val = typeof raw === "object" ? (raw.id ?? raw) : raw;
    if (val != null && String(val).trim()) params.append("vacancy_id", String(val).trim());
  }
  if (search) params.append("search", search);
  if (category) params.append("category", String(category));
  if (is_perfect_candidate === true) {
    params.append("is_perfect_candidate", "true");
  }
  params.append("page", String(page + 1));
  params.append("per_page", String(per_page));

  return http.get(`/candidates?${params.toString()}`, opts);
};

export const getCandidate = (id) => http.get(`/candidate/${id}`);
export const createCandidate = (data) => http.post("/candidate", data);
export const updateCandidate = (id, data = {}) => {
    const payload = { ...data };
    if (payload.status != null) {
        payload.status = normalizeStatusForBackendValue(payload.status);
    }
    return http.patch(`/candidate/${id}`, payload);
};
export const deleteCandidate = (id) => http.del(`/candidate/${id}`);


export const getCandidateStatus = async (candidateId) => {
    const data = await http.get(`/candidate/${candidateId}/status`);
    if (typeof data === 'string') return data;
    return data?.status ?? data?.status_name ?? data?.status_code ?? null;
};

export const createTestResult = (data) => http.post("/test/results", data)
export const createQuestionAnswer = (data) => http.post("/test/question-answers", data)
export const getTestResults = (id) => http.get(`/candidate/${id}/results`)

export const assignVacancyToCandidate = (candidateId, vacancyId, status = "откликнулся", isActive = true) =>
    http.post("/candidate/vacancy", {
        candidate_id: candidateId,
        vacancy_id: vacancyId,
        status: status,
        is_active: isActive
    });

export const changeCandidateVacancy = (candidateId, vacancyId) =>
    http.post("/candidate/vacancy/change", {
        candidate_id: Number(candidateId),
        vacancy_id: Number(vacancyId),
    });

export const sendCandidateNotification = (candidateId, vacancyId) =>
    http.post("/candidate/new-vacancy", { candidate_id: candidateId, vacancy_id: vacancyId });

export const updateCandidateStatus = (candidateId, status) =>
    http.put(`/candidate/${candidateId}/status`, { status });

export const archiveCandidate = (candidateId) =>
    http.put(`/candidate/${candidateId}/archive`);

export const blacklistCandidate = (candidateId) =>
    http.put(`/candidate/${candidateId}/blacklist`);

export const hireCandidate = (candidateId) =>
    http.put(`/candidate/${candidateId}/hire`);

/** Route hire to stage endpoint; archive-like statuses are handled by PUT /status. */
export const applyCandidateStatus = async (candidateId, status) => {
    const value = normalizeStatusForBackendValue(status);
    const normalized = String(value ?? "").trim();

    if (normalized === "ВНР" || normalized === "Нанят") {
        return hireCandidate(candidateId);
    }
    return updateCandidateStatus(candidateId, normalized);
};

// понадобится для шага 4 в CandidateDetails
export const getCandidateById = (candidateId) =>
    http.get(`/candidate/${candidateId}`);

export const startCandidateExercise = (candidateId, instructionText, minutes) => {
    return http.post("/candidate/exercise", {
        candidate_id: candidateId,
        instruction_text: instructionText,
        minutes: minutes,
    });
}

export const sendOffer = (candidateId, offerText, includeDocumentsLink = false) =>
    http.post("/candidate/offer", { candidate_id: candidateId, offer_text: offerText, include_documents_link: includeDocumentsLink });

export const sendInterviewInvite = (candidateId, payload = {}) =>
    http.post("/candidate/interview-invite", {
        candidate_id: Number(candidateId),
        message: payload.message,
        hr_id: payload.hr_id || null,
        interview_date: payload.interview_date || null,
        start_time: payload.start_time || null,
        end_time: payload.end_time || null,
        book_calendar: payload.book_calendar !== false,
        remind_candidate: Boolean(payload.remind_candidate),
        remind_at: payload.remind_at || null,
        reminder_message: payload.reminder_message || null,
    });

export const sendProfessionalTestToCandidate = (candidateId, testId, message = null) =>
    http.post("/candidate/professional-test/send", {
        candidate_id: Number(candidateId),
        test_id: Number(testId),
        ...(message ? { message } : {}),
    });

export const getArchivedCandidates = () => http.get("/candidates/archived");

export const getBlacklistedCandidates = () => http.get("/candidates/blacklisted");

export const getCandidateActiveVacancy = (candidateId) =>
    http.get(`/candidate/${candidateId}/active-vacancy`);

export const getCandidateVacancies = (candidateId) =>
    http.get(`/candidate/${candidateId}/vacancies`);

/** Vacancy the candidate applied to (active relation, else latest linked vacancy). */
export async function loadCandidateVacancyTitle(candidateId) {
    if (candidateId == null || candidateId === "") return null;
    try {
        const rel = await getCandidateActiveVacancy(candidateId);
        const name = relationVacancyName(rel);
        if (name) return name;
    } catch (_) {
        /* 404: no active vacancy */
    }
    try {
        const data = await getCandidateVacancies(candidateId);
        const arr = Array.isArray(data) ? data : (data?.items ?? []);
        if (!arr.length) return null;
        const active = arr.find((r) => r?.is_active);
        const chosen = active || [...arr].sort((a, b) => Number(b.id || 0) - Number(a.id || 0))[0];
        return relationVacancyName(chosen);
    } catch (_) {
        return null;
    }
}
