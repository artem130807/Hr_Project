/**
 * @jest-environment node
 */
import { computeRisk, computeStatus, overdueStartsAt, planDateFor, rolesForKind } from "./rules";
import { checkpointDateBucket, filterCheckpoints } from "./filters";
import { managerSafeReport } from "./reports";

describe("adaptation rules", () => {
    it("plans week and month checkpoints from hire date", () => {
        const hired = new Date(2026, 5, 17);
        expect(planDateFor("week_1", hired).getDate()).toBe(24);
        expect(planDateFor("month_1", hired).getMonth()).toBe(6);
        expect(planDateFor("month_2", hired).getMonth()).toBe(7);
    });

    it("mutes manager on week 1 and keeps control HR-only", () => {
        expect(rolesForKind("week_1")).toEqual(["employee", "hr"]);
        expect(rolesForKind("control_2m")).toEqual(["hr"]);
        expect(rolesForKind("month_2")).toContain("manager");
    });

    it("marks overdue from 09:00 the next calendar day", () => {
        const plan = new Date(2026, 7, 23);
        const start = overdueStartsAt(plan);
        expect(start.getDate()).toBe(24);
        expect(start.getHours()).toBe(9);
        const before = new Date(2026, 7, 24, 8, 59);
        const after = new Date(2026, 7, 24, 9, 0);
        expect(computeStatus({ kind: "month_2", planDate: plan, answers: [], now: before })).toBe("collecting");
        expect(computeStatus({ kind: "month_2", planDate: plan, answers: [], now: after })).toBe("overdue");
    });

    it("computes risk bands from Likert", () => {
        expect(computeRisk({ a: 5, b: 4 }, "month_2")).toBe("low");
        expect(computeRisk({ a: 3, b: 3 }, "month_2")).toBe("medium");
        expect(computeRisk({ a: 1, b: 2 }, "month_2")).toBe("high");
        expect(computeRisk({}, "month_2")).toBe("uncalculated");
        expect(computeRisk({ core_e1: 5, core_e2: 5, core_e3: 4, core_e4: 4, core_e5: 5 }, "month_1")).toBe("low");
        expect(computeRisk({ core_e1: 2, core_e2: 2, core_e3: 4, core_e4: 4, core_e5: 5 }, "month_1")).toBe("high");
    });

    it("shifts weekend plan dates to the next weekday", () => {
        const hired = new Date(2026, 0, 31);
        const month1 = planDateFor("month_1", hired);
        expect(month1.getMonth()).toBe(2);
        expect(month1.getDate()).toBe(2);
        expect(planDateFor("extra", hired, new Date(2026, 7, 29)).getDate()).toBe(31);
    });

    it("does not score control checkpoints; uses core scales when present", () => {
        expect(computeRisk({ c2_ok: true }, "control_2m")).toBe("uncalculated");
        expect(computeRisk({ m1_role: 5, m1_doubts: 5 }, "month_1")).toBe("low");
    });
});

describe("adaptation filters and reports", () => {
    const rows = [
        { full_name: "Касумов", position: "Логист", department: "Логистика", kind: "month_2", risk: "medium", status: "collecting" },
        { full_name: "Белогубов", position: "Инженер", department: "IT", kind: "month_2", risk: "low", status: "completed" },
    ];

    it("filters by search and hide completed", () => {
        expect(filterCheckpoints(rows, { q: "касум" })).toHaveLength(1);
        expect(filterCheckpoints(rows, { hideCompleted: true })).toHaveLength(1);
        expect(filterCheckpoints(rows, { department: "IT" })[0].full_name).toBe("Белогубов");
    });

    it("filters checkpoints by clear date buckets", () => {
        const today = new Date(2026, 8, 10, 15, 0, 0);
        expect(checkpointDateBucket("2026-09-09", today)).toBe("overdue");
        expect(checkpointDateBucket("2026-09-10", today)).toBe("today");
        expect(checkpointDateBucket("2026-09-24", today)).toBe("two_weeks");
        expect(checkpointDateBucket("2026-09-25", today)).toBe("later");

        const datedRows = [
            { full_name: "A", plan_date: "2026-09-09" },
            { full_name: "B", plan_date: "2026-09-10" },
            { full_name: "C", plan_date: "2026-09-20" },
        ];
        expect(filterCheckpoints(datedRows, { dateScope: "today" }, today).map((row) => row.full_name)).toEqual(["B"]);
        expect(filterCheckpoints(datedRows, { dateScope: "two_weeks" }, today).map((row) => row.full_name)).toEqual(["C"]);
    });

    it("does not leak employee free text into manager report", () => {
        const safe = managerSafeReport({
            full_name: "Иванов",
            kind: "month_2",
            answers: [
                { role: "employee", payload: { m2_issues: "хочу уволиться" } },
                { role: "hr", payload: { hr_notes: "Внутренняя заметка", hr_comment: "Конфиденциально", manager_summary: "Нужен наставник" } },
            ],
        });
        expect(JSON.stringify(safe)).not.toContain("хочу уволиться");
        expect(JSON.stringify(safe)).not.toContain("Конфиденциально");
        expect(JSON.stringify(safe)).not.toContain("Внутренняя заметка");
        expect(safe.hr_notes).toBe("Нужен наставник");
    });
});
