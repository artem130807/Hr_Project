import { appAbsoluteUrl, appBasePath, appPath } from "./publicUrl";

describe("GitHub Pages public paths", () => {
    const originalPublicUrl = process.env.PUBLIC_URL;

    afterEach(() => {
        process.env.PUBLIC_URL = originalPublicUrl;
    });

    it("keeps root-hosted paths unchanged", () => {
        process.env.PUBLIC_URL = "";
        expect(appBasePath()).toBe("");
        expect(appPath("/calendar")).toBe("/calendar");
    });

    it("prefixes project-site paths", () => {
        process.env.PUBLIC_URL = "/Hr_Project";
        expect(appBasePath()).toBe("/Hr_Project");
        expect(appPath("/calendar")).toBe("/Hr_Project/calendar");
        expect(appAbsoluteUrl("/calendar", "https://artem130807.github.io"))
            .toBe("https://artem130807.github.io/Hr_Project/calendar");
    });
});
