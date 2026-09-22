import { resolvePublicApiUrl } from "./api";

describe("resolvePublicApiUrl", () => {
    it("ignores prod URL during npm start (development)", () => {
        expect(
            resolvePublicApiUrl({
                nodeEnv: "development",
                configured: "https://hr-platform.alt-cargo.tw1.ru",
            })
        ).toBe("");
    });

    it("uses same-origin on hr-web even if CI baked a remote API URL", () => {
        expect(
            resolvePublicApiUrl({
                nodeEnv: "production",
                hostname: "hr-web.alt-cargo.tw1.ru",
                configured: "https://hr-platform.alt-cargo.tw1.ru",
            })
        ).toBe("");
    });

    it("uses configured host on unknown production hosts", () => {
        expect(
            resolvePublicApiUrl({
                nodeEnv: "production",
                hostname: "alt-lovat.vercel.app",
                configured: "https://hr-platform.alt-cargo.tw1.ru/",
            })
        ).toBe("https://hr-platform.alt-cargo.tw1.ru");
    });

    it("allows opting into remote API locally", () => {
        expect(
            resolvePublicApiUrl({
                nodeEnv: "development",
                forceRemote: "true",
                configured: "https://hr-platform.alt-cargo.tw1.ru",
            })
        ).toBe("https://hr-platform.alt-cargo.tw1.ru");
    });
});
