/**
 * @jest-environment jsdom
 */
import { formatExperienceMonths, mapHhResumeToProfile, resumeUpdatedLabel } from "./hhNegotiationResume";

describe("hhNegotiationResume", () => {
    it("formats months as years and months", () => {
        expect(formatExperienceMonths(76)).toBe("6 г. 4 мес.");
        expect(formatExperienceMonths(12)).toBe("1 г.");
        expect(formatExperienceMonths(null)).toBeNull();
    });

    it("maps HH resume into candidate profile without AI fields", () => {
        const profile = mapHhResumeToProfile(
            {
                last_name: "Юдинцев",
                first_name: "Богдан",
                middle_name: "Сергеевич",
                age: 21,
                birth_date: "2005-07-01",
                area: "Самара",
                skill_set: ["Python", "FastAPI"],
                experience: [{ title: "Стажёр", company: "ООО", period: "2024 — н.в." }],
                education: ["СамГТУ"],
                languages: ["Русский — родной"],
                salary_amount: 80000,
                salary_currency: "RUR",
                experience_months: 12,
                about: "Backend",
            },
            { vacancyName: "Стажер-разработчик Python" }
        );
        expect(profile.full_name).toBe("Юдинцев Богдан Сергеевич");
        expect(profile.vacancy_name).toBe("Стажер-разработчик Python");
        expect(profile.hard_skills).toEqual(["Python", "FastAPI"]);
        expect(profile.ai_score).toBeUndefined();
        expect(profile.experience_label).toBe("1 г.");
        expect(profile.experience[0].company).toBe("ООО");
    });

    it("labels recent resume updates", () => {
        const recent = new Date(Date.now() - 3 * 86400000).toISOString();
        expect(resumeUpdatedLabel(recent)).toBe("до 7 дней");
    });
});
