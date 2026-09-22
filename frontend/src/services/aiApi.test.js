/**
 * @jest-environment jsdom
 */
import { generateDescriptionAndSalary } from "./aiApi";
import { fetchWithAuth } from "../utils/fetchWithAuth";

jest.mock("../utils/fetchWithAuth", () => ({
    fetchWithAuth: jest.fn(),
}));

describe("aiApi", () => {
    it("posts vacancy description-salary combine payload", async () => {
        fetchWithAuth.mockResolvedValue({
            ok: true,
            json: async () => ({ description: "text", salary_from: 100000, salary_to: 150000 }),
        });
        const result = await generateDescriptionAndSalary("Логист, Москва");
        expect(result.salary_from).toBe(100000);
        const [url, options] = fetchWithAuth.mock.calls[0];
        expect(url).toContain("/vacancy/description-salary-combine");
        expect(JSON.parse(options.body).formatted_vacancy).toBe("Логист, Москва");
    });

    it("throws when AI proxy returns an error", async () => {
        fetchWithAuth.mockResolvedValue({
            ok: false,
            status: 503,
            text: async () => "AI service is not configured",
        });
        await expect(generateDescriptionAndSalary("x")).rejects.toThrow("HTTP error");
    });
});
