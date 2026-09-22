import { publicAdaptationFormUrl } from "./publicFormLink";

describe("publicAdaptationFormUrl", () => {
    it("builds an absolute current-frontend URL and encodes the token", () => {
        expect(publicAdaptationFormUrl("token / one")).toBe(
            "http://localhost/adaptation/forms/token%20%2F%20one"
        );
    });

    it("prefers a valid URL supplied by the backend", () => {
        expect(publicAdaptationFormUrl("ignored", "https://hr.example.ru/adaptation/forms/abc")).toBe(
            "https://hr.example.ru/adaptation/forms/abc"
        );
    });
});
