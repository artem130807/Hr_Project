import { AI_API_URL, API_PREFIX } from "../config/api";
import { fetchWithAuth } from "../utils/fetchWithAuth";

async function fetchAI(path, options = {}) {
    const url = `${AI_API_URL}${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;

    const response = await fetchWithAuth(url, options);

    if (!response.ok) {
        const errorText = await response.text();
        console.error("AI API Error:", errorText);
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
}

export const generateTest = (topic, formattedVacancy) =>
    fetchAI("/test/generate", {
        method: "POST",
        body: JSON.stringify({
            topic,
            formatted_vacancy: formattedVacancy,
        }),
    });

export const generateDescriptionAndSalary = (formattedVacancy) =>
    fetchAI("/vacancy/description-salary-combine", {
        method: "POST",
        body: JSON.stringify({
            formatted_vacancy: formattedVacancy,
        }),
    });
