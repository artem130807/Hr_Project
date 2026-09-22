import {
    __resetNotificationsMock,
    mockFetchMessages,
    mockFetchUnreadCount,
    mockMarkMessagesAsRead,
    pushMockNotification,
    subscribeMockNotifications,
} from "./notificationsMock";
import {
    fetchMessages,
    fetchUnreadCount,
    markMessageAsRead,
    markMessagesAsRead,
} from "./notificationsApi";

describe("notificationsMock + api", () => {
    beforeEach(() => {
        __resetNotificationsMock({
            messages: [
                {
                    id: 1,
                    content: "A",
                    is_read: false,
                    user_id: "1",
                    role: null,
                    channel_id: null,
                    entity_type: "vacancy",
                    entity_id: 1,
                    created_at: "2026-08-14T10:00:00Z",
                },
                {
                    id: 2,
                    content: "B",
                    is_read: false,
                    user_id: null,
                    role: "hr",
                    channel_id: 1,
                    entity_type: "hiring_request",
                    entity_id: 2,
                    created_at: "2026-08-14T11:00:00Z",
                },
            ],
            channels: [{ id: 1, name: "Заявки", entity_type: "hiring_request", entity_id: 0 }],
            settings: [{ id: 1, channel_id: 1, is_send_push_message: true }],
            nextId: 3,
            nextSettingId: 2,
        });
    });

    it("counts unread", async () => {
        expect(await mockFetchUnreadCount()).toEqual({ count: 2 });
        expect(await fetchUnreadCount()).toBe(2);
    });

    it("filters personal and role lists", async () => {
        const personal = await fetchMessages({ user_id: "1" });
        expect(personal).toHaveLength(1);
        expect(personal[0].content).toBe("A");
        const role = await mockFetchMessages({ role: "hr" });
        expect(role).toHaveLength(1);
        expect(role[0].content).toBe("B");
    });

    it("marks matching messages as read", async () => {
        const marked = await markMessagesAsRead({ user_id: "1" });
        expect(marked).toBe(1);
        expect(await fetchUnreadCount()).toBe(1);
        const list = await mockFetchMessages({ user_id: "1" });
        expect(list[0].is_read).toBe(true);
    });

    it("marks one message as read", async () => {
        const updated = await markMessageAsRead(1);
        expect(updated.is_read).toBe(true);
        expect((await mockFetchMessages({ user_id: "1" }))[0].is_read).toBe(true);
    });

    it("subscribe receives pushed notifications", () => {
        const received = [];
        const unsub = subscribeMockNotifications((m) => received.push(m));
        pushMockNotification({ content: "Ping", user_id: "1" });
        expect(received).toHaveLength(1);
        expect(received[0].content).toBe("Ping");
        unsub();
    });

    it("fetches channels and toggles settings via api facade", async () => {
        const {
            fetchUserChannels,
            fetchUserSettings,
            updateChannelSettings,
            createChannelSettings,
        } = require("./notificationsApi");

        const channels = await fetchUserChannels();
        expect(channels).toHaveLength(1);
        expect(channels[0].name).toBe("Заявки");

        const settings = await fetchUserSettings();
        expect(settings[0].is_send_push_message).toBe(true);

        const updated = await updateChannelSettings(1, { is_send_push_message: false });
        expect(updated.is_send_push_message).toBe(false);

        const created = await createChannelSettings({
            channel_id: 99,
            is_send_push_message: true,
        });
        expect(created.channel_id).toBe(99);
        expect(created.id).toBe(2);
    });

    it("emitDemoNotification pushes through mock bus", () => {
        const { emitDemoNotification } = require("./notificationsApi");
        const received = [];
        const unsub = subscribeMockNotifications((m) => received.push(m));
        emitDemoNotification({ content: "Demo", role: "hr" });
        expect(received[0].content).toBe("Demo");
        unsub();
    });
});
