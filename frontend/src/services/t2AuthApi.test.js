jest.mock("../config/api", () => ({
    API_URL: "http://api.test",
    API_PREFIX: "/v1",
}));

jest.mock("../utils/http", () => ({
    http: {
        get: jest.fn(),
        put: jest.fn(),
        del: jest.fn(),
    },
}));

const { http } = require("../utils/http");
const { getT2OAuthTokens, putT2OAuthTokens, isT2AtsConnected } = require("./t2AuthApi");

describe("t2AuthApi", () => {
    beforeEach(() => {
        http.get.mockReset();
        http.put.mockReset();
        http.get.mockResolvedValue({ payload: null });
        http.put.mockResolvedValue({ payload: { access_token: "a", refresh_token: "r" } });
    });

    it("loads and saves tokens on /t2-oauth/tokens", async () => {
        await getT2OAuthTokens();
        expect(http.get).toHaveBeenCalledWith("/t2-oauth/tokens");
        await putT2OAuthTokens({ access_token: "acc", refresh_token: "ref" });
        expect(http.put).toHaveBeenCalledWith("/t2-oauth/tokens", {
            access_token: "acc",
            refresh_token: "ref",
        });
    });

    it("detects a connected ATS pair", () => {
        expect(isT2AtsConnected({ payload: { access_token: "a", refresh_token: "r" } })).toBe(true);
        expect(isT2AtsConnected({ payload: { access_token: "a" } })).toBe(false);
        expect(isT2AtsConnected({ payload: null })).toBe(false);
    });
});
