/**
 * @jest-environment node
 */
import { enrollAdaptation, generateAdaptationDocuments, getAdaptationTakeLinks, getPublicAdaptationForm, listAdaptationCheckpoints, rotateAdaptationFormToken, submitPublicAdaptationForm } from "./adaptationApi";
import { http } from "../utils/http";

jest.mock("../utils/http", () => ({
    http: { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), getBlob: jest.fn() },
}));

describe("adaptationApi", () => {
    it("lists checkpoints with query params", async () => {
        http.get.mockResolvedValue({ items: [] });
        await listAdaptationCheckpoints({ year: 2026, month: 8, hide_completed: true });
        expect(http.get).toHaveBeenCalledWith(
            "/adaptation/checkpoints?year=2026&month=8&hide_completed=true"
        );
    });

    it("posts enrollment", async () => {
        http.post.mockResolvedValue({ id: 1 });
        await enrollAdaptation({ erp_user_id: "erp-uuid-1", include_control_2m: false });
        expect(http.post).toHaveBeenCalledWith("/adaptation/enrollments", {
            erp_user_id: "erp-uuid-1",
            include_control_2m: false,
        });
    });

    it("loads take links for an enrollment", async () => {
        http.get.mockResolvedValue({ links: [] });
        await getAdaptationTakeLinks(12);
        expect(http.get).toHaveBeenCalledWith("/adaptation/enrollments/12/take-links");
        await getAdaptationTakeLinks(12, true);
        expect(http.get).toHaveBeenCalledWith("/adaptation/enrollments/12/take-links?include_internal=true");
    });

    it("rotates a take link only through an explicit endpoint", async () => {
        http.post.mockResolvedValue({ form_id: 4, revoked_previous: true });
        await rotateAdaptationFormToken(4, { confirmed: true, reason: "Ссылка раскрыта" });
        expect(http.post).toHaveBeenCalledWith("/adaptation/forms/4/rotate-token", { confirmed: true, reason: "Ссылка раскрыта" });
    });

    it("uses unauthenticated personal form endpoints", async () => {
        await getPublicAdaptationForm("token / 1");
        expect(http.get).toHaveBeenCalledWith("/public/adaptation/forms/token%20%2F%201", { auth: false });
        await submitPublicAdaptationForm("abc", { q1: 5 });
        expect(http.post).toHaveBeenCalledWith("/public/adaptation/forms/abc", { payload: { q1: 5 } }, { auth: false });
    });

    it("requests deterministic versioned documents", async () => {
        const payload = { formats: ["docx", "pdf"], idempotency_key: "click-1" };
        await generateAdaptationDocuments(9, payload);
        expect(http.post).toHaveBeenCalledWith("/adaptation/checkpoints/9/documents", payload);
    });
});
