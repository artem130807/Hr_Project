import {http} from "../utils/http";
import { documentFilename } from "../utils/documentFilename";

export const getActiveCandidates = (vacancyId = null) => {
    const params = new URLSearchParams();
    if (vacancyId != null && String(vacancyId).trim()) {
        params.append("vacancy_id", String(vacancyId).trim());
    }
    const qs = params.toString();
    return http.get(`/analytics/active-candidates${qs ? `?${qs}` : ""}`);
};

export const getDashboard = () => http.get("/analytics/dashboard");

export const getHrProfileStats = (hrUserId = null) => {
    const params = new URLSearchParams();
    if (hrUserId != null && String(hrUserId).trim()) {
        params.set("hr_user_id", String(hrUserId).trim());
    }
    const qs = params.toString();
    return http.get(`/analytics/hr-profile${qs ? `?${qs}` : ""}`);
};

export const getStatuses = () => http.get("/dict/status");

export const exportAnalyticsTable = async (from, to, vacancyId = null) => {
    const params = new URLSearchParams();
    if (from) params.append("date_from", from);
    if (to) params.append("date_to", to);
    if (vacancyId != null && String(vacancyId).trim()) {
        params.append("vacancy_id", String(vacancyId).trim());
    }
    const qs = params.toString();
    const path = qs ? `/analytics/funnel/export?${qs}` : "/analytics/funnel/export";
    const blob = await http.getBlob(path);
    const objectUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    const period = [from, to].filter(Boolean).join("–");
    a.download = documentFilename({
        type: "Воронка кандидатов",
        stage: period,
        date: null,
        id: vacancyId,
        extension: "xlsx",
    });
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(objectUrl);
};
