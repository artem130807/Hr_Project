import {
    parseWorkExperienceList,
    describeStatusEvent,
    mergeCandidateTimeline,
    actorLabel,
} from "./candidateActivity";

describe("candidateActivity", () => {
    it("parses labeled HH experience blocks", () => {
        const [job] = parseWorkExperienceList([
            "Должность: Логист\nКомпания: ООО Ромашка\nПериод: 2020-01-01 — 2022-06-01\nОписание: Перевозки",
        ]);
        expect(job.title).toBe("Логист");
        expect(job.company).toBe("ООО Ромашка");
        expect(job.period).toBe("2020-01-01 — 2022-06-01");
        expect(job.description).toBe("Перевозки");
    });

    it("keeps plain experience strings readable", () => {
        const [job] = parseWorkExperienceList(["Водитель 2 года"]);
        expect(job.title).toBe("Водитель 2 года");
    });

    it("describes status change with actor", () => {
        expect(describeStatusEvent({
            actor_name: "Анна Смирнова",
            from_status: "откликнулся",
            to_status: "собес",
        })).toBe("Анна Смирнова сменил(а) статус с «откликнулся» на «собес»");
    });

    it("merges timeline newest first", () => {
        const events = mergeCandidateTimeline({
            history: [{ id: 1, created_at: "2026-01-01T10:00:00Z", to_status: "собес", actor_name: "HR" }],
            comments: [{ id: 2, created_at: "2026-01-02T10:00:00Z", author_name: "Lead", body: "Ок" }],
            approvals: [{ id: 3, created_at: "2026-01-03T10:00:00Z", approver_name: "Owner", new_status: "Одобрен собственником" }],
        });
        expect(events.map((e) => e.type)).toEqual(["approval", "comment", "status"]);
        expect(actorLabel("")).toBe("Система");
    });
});
