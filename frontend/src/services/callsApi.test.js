jest.mock("../config/api", () => ({
    API_URL: "http://api.test",
    API_PREFIX: "/v1",
}));

jest.mock("../utils/http", () => ({
    http: {
        get: jest.fn(),
    },
}));

describe("callsApi", () => {
    beforeEach(() => {
        const { http } = require("../utils/http");
        http.get.mockReset();
        http.get.mockResolvedValue([]);
    });

    it("requests the conversations list with query params", async () => {
        const { http } = require("../utils/http");
        const { getCallConversations } = require("./callsApi");
        await getCallConversations({ limit: 50, offset: 10, status: "pending" });
        expect(http.get).toHaveBeenCalledWith(
            "/call-conversations?limit=50&offset=10&status=pending"
        );
    });

    it("omits empty filters", async () => {
        const { http } = require("../utils/http");
        const { getCallConversations } = require("./callsApi");
        await getCallConversations();
        expect(http.get).toHaveBeenCalledWith("/call-conversations");
    });

    it("loads a single conversation by id", async () => {
        const { http } = require("../utils/http");
        http.get.mockResolvedValue({ id: 9, filename: "a.mp3" });
        const { getCallConversation } = require("./callsApi");
        const row = await getCallConversation(9);
        expect(http.get).toHaveBeenCalledWith("/call-conversations/9");
        expect(row.filename).toBe("a.mp3");
    });
});
