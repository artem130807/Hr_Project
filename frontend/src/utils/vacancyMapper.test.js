import { mapVacancyToBackend, mapVacancyFromBackend } from "./vacancyMapper";

describe("vacancyMapper", () => {
    describe("mapVacancyToBackend", () => {
        it("maps employment_type and work_format to backend ids", () => {
            const result = mapVacancyToBackend({
                name: "Логист",
                gender: "мужчина",
                department: "it",
                employment_type: "full",
                work_format: "fullDay",
                total_work_expirience: "1-3 года",
                professional_role_id: 67,
            });

            expect(result.gender).toBe("male");
            expect(result.department).toBe("IT");
            expect(result.employment_id).toBe("full");
            expect(result.schedule_id).toBe("fullDay");
            expect(result.total_work_expirience).toBe("between1And3");
            expect(result.professional_roles_id).toEqual(["67"]);
            expect(result.employment_type).toBeUndefined();
            expect(result.work_format).toBeUndefined();
            expect(result.professional_role_id).toBeUndefined();
        });

        it("keeps HH experience ids as-is", () => {
            const result = mapVacancyToBackend({
                total_work_expirience: "noExperience",
            });
            expect(result.total_work_expirience).toBe("noExperience");
        });
    });

    describe("mapVacancyFromBackend", () => {
        it("maps backend fields back to form aliases without reversing experience ids", () => {
            const result = mapVacancyFromBackend({
                gender: "female",
                employment_id: "full",
                schedule_id: "remote",
                total_work_expirience: "between1And3",
                professional_roles_id: ["42"],
            });

            expect(result.gender).toBe("женщина");
            expect(result.employment_type).toBe("full");
            expect(result.work_format).toBe("remote");
            expect(result.total_work_expirience).toBe("between1And3");
            expect(result.professional_role_id).toBe(42);
        });
    });
});
