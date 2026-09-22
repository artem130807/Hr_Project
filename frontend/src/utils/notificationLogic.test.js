import {
    NOTIFICATION_VIEWS,
    buildChannelMessagesParams,
    buildPersonalMessagesParams,
    buildRoleMessagesParams,
    findSettingsForChannel,
    formatRelativeTime,
    formatUnreadBadge,
    hasMessageFilterParams,
    loadMessagesWithMarkRead,
    parseMarkReadPayload,
    parseUnreadCountPayload,
    roleSectionTitle,
    shouldMarkMessagesAsRead,
    viewMarksMessagesAsRead,
} from "./notificationLogic";

describe("notificationLogic", () => {
    it("roleSectionTitle uses HR role labels", () => {
        expect(roleSectionTitle("hr")).toBe("Уведомления: HR");
        expect(roleSectionTitle("owner")).toBe("Уведомления: Собственник");
        expect(roleSectionTitle("  ")).toBe("Уведомления для роли");
    });

    it("formatUnreadBadge caps at 99+", () => {
        expect(formatUnreadBadge(0)).toBe("");
        expect(formatUnreadBadge(3)).toBe("3");
        expect(formatUnreadBadge(99)).toBe("99");
        expect(formatUnreadBadge(120)).toBe("99+");
    });

    it("builds message filter params", () => {
        expect(buildPersonalMessagesParams(42)).toEqual({ user_id: "42" });
        expect(buildPersonalMessagesParams(null)).toBeNull();
        expect(buildRoleMessagesParams("hr")).toEqual({ role: "hr" });
        expect(buildRoleMessagesParams("")).toBeNull();
        expect(buildChannelMessagesParams(12)).toEqual({ channel_id: 12 });
        expect(buildChannelMessagesParams(0)).toBeNull();
    });

    it("hasMessageFilterParams rejects empty object", () => {
        expect(hasMessageFilterParams(null)).toBe(false);
        expect(hasMessageFilterParams({})).toBe(false);
        expect(hasMessageFilterParams({ role: "hr" })).toBe(true);
    });

    it("findSettingsForChannel matches channel_id", () => {
        const settings = [
            { id: 1, channel_id: 10, is_send_push_message: true },
            { id: 2, channel_id: 20, is_send_push_message: false },
        ];
        expect(findSettingsForChannel(settings, 20)?.id).toBe(2);
        expect(findSettingsForChannel(settings, 99)).toBeNull();
    });

    it("parses unread / mark payloads", () => {
        expect(parseUnreadCountPayload({ count: 7 })).toBe(7);
        expect(parseUnreadCountPayload(3)).toBe(3);
        expect(parseUnreadCountPayload(null)).toBe(0);
        expect(parseMarkReadPayload({ marked: 4 })).toBe(4);
        expect(parseMarkReadPayload(2)).toBe(2);
    });

    it("formatRelativeTime recent", () => {
        const now = Date.parse("2026-08-11T12:00:00Z");
        expect(formatRelativeTime("2026-08-11T11:59:30Z", now)).toBe("только что");
        expect(formatRelativeTime("2026-08-11T11:40:00Z", now)).toBe("20 мин назад");
    });

    it("viewMarksMessagesAsRead only for message lists", () => {
        expect(viewMarksMessagesAsRead(NOTIFICATION_VIEWS.PERSONAL)).toBe(true);
        expect(viewMarksMessagesAsRead(NOTIFICATION_VIEWS.ROLE)).toBe(true);
        expect(viewMarksMessagesAsRead(NOTIFICATION_VIEWS.CHANNEL)).toBe(true);
        expect(viewMarksMessagesAsRead(NOTIFICATION_VIEWS.MENU)).toBe(false);
        expect(viewMarksMessagesAsRead(NOTIFICATION_VIEWS.CHANNELS)).toBe(false);
    });

    it("shouldMarkMessagesAsRead requires enabled params and list view", () => {
        expect(shouldMarkMessagesAsRead(true, { user_id: "u" }, NOTIFICATION_VIEWS.PERSONAL)).toBe(true);
        expect(shouldMarkMessagesAsRead(true, { role: "hr" }, NOTIFICATION_VIEWS.ROLE)).toBe(true);
        expect(shouldMarkMessagesAsRead(false, { user_id: "u" }, NOTIFICATION_VIEWS.PERSONAL)).toBe(false);
        expect(shouldMarkMessagesAsRead(true, null, NOTIFICATION_VIEWS.PERSONAL)).toBe(false);
        expect(shouldMarkMessagesAsRead(true, { user_id: "u" }, NOTIFICATION_VIEWS.MENU)).toBe(false);
    });

    it("loadMessagesWithMarkRead marks before fetch and normalizes is_read", async () => {
        const calls = [];
        const { list, marked } = await loadMessagesWithMarkRead({
            params: { user_id: "u1" },
            view: NOTIFICATION_VIEWS.PERSONAL,
            markRead: async (params) => {
                calls.push(["mark", params]);
            },
            fetchList: async (params) => {
                calls.push(["fetch", params]);
                return [
                    { id: 1, content: "a", is_read: false },
                    { id: 2, content: "b", is_read: true },
                ];
            },
        });
        expect(calls.map((c) => c[0])).toEqual(["mark", "fetch"]);
        expect(marked).toBe(true);
        expect(list[0].is_read).toBe(true);
        expect(list[1].is_read).toBe(true);
    });

    it("loadMessagesWithMarkRead skips mark on menu view", async () => {
        const calls = [];
        const { list, marked } = await loadMessagesWithMarkRead({
            params: { user_id: "u1" },
            view: NOTIFICATION_VIEWS.MENU,
            markRead: async () => {
                calls.push("mark");
            },
            fetchList: async () => {
                calls.push("fetch");
                return [{ id: 1, is_read: false }];
            },
        });
        expect(calls).toEqual(["fetch"]);
        expect(marked).toBe(false);
        expect(list[0].is_read).toBe(false);
    });

    it("loadMessagesWithMarkRead still fetches when mark fails", async () => {
        const { list, marked } = await loadMessagesWithMarkRead({
            params: { role: "hr" },
            view: NOTIFICATION_VIEWS.ROLE,
            markRead: async () => {
                throw new Error("network");
            },
            fetchList: async () => [{ id: 1, is_read: false }],
        });
        expect(marked).toBe(false);
        expect(list).toHaveLength(1);
        expect(list[0].is_read).toBe(false);
    });
});
