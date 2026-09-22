import {
    buildNotificationsWsURL,
    notificationIsPersonalForUser,
    notificationIsVisibleForUser,
    notificationIsNavigable,
    notificationKind,
    notificationRoutePath,
    notificationToastMessage,
    parseNotificationPayload,
} from "./notificationWsLogic";

describe("notificationWsLogic", () => {
    it("builds ws url from relative and absolute base", () => {
        expect(
            buildNotificationsWsURL("/notifications", "tok", {
                protocol: "ws:",
                host: "localhost:3000",
            })
        ).toBe("ws://localhost:3000/notifications/api/ws?token=tok");

        expect(
            buildNotificationsWsURL("https://msg.example.com", "a b", {
                protocol: "ws:",
                host: "ignored",
            })
        ).toBe("wss://msg.example.com/api/ws?token=a%20b");

        expect(buildNotificationsWsURL("/notifications", "")).toBeNull();
    });

    it("parses payload and HR routes", () => {
        const parsed = parseNotificationPayload(
            JSON.stringify({
                type: "notification",
                id: 1,
                content: "Новая заявка",
                channel_id: 5,
                entity_type: "hiring_request",
                entity_id: 42,
            })
        );
        expect(parsed.content).toBe("Новая заявка");
        expect(parsed.channel_id).toBe(5);
        expect(parsed.entity_type).toBe("hiring_request");
        expect(parsed.entity_id).toBe(42);
        expect(notificationKind(parsed)).toBe("channel");
        expect(notificationToastMessage(parsed)).toBe("Новая заявка");
        expect(notificationRoutePath(parsed)).toBe("/requests");
        expect(notificationIsNavigable(parsed)).toBe(true);
    });

    it("maps HR entity types", () => {
        expect(notificationRoutePath({ entity_type: "vacancy", entity_id: 7 })).toBe("/vacancies");
        expect(notificationRoutePath({ entity_type: "candidate", entity_id: 1 })).toBe("/candidates");
        expect(notificationRoutePath({ entity_type: "employee", entity_id: 3 })).toBe("/employees");
        expect(notificationRoutePath({ entity_type: "event", entity_id: 2 })).toBe("/events");
        expect(notificationRoutePath({ entity_type: "unknown", entity_id: 1 })).toBeNull();
        expect(notificationRoutePath({ entity_type: "vacancy", entity_id: 0 })).toBeNull();
        expect(notificationIsNavigable({ content: "x" })).toBe(false);
    });

    it("rejects invalid payloads", () => {
        expect(parseNotificationPayload("{bad")).toBeNull();
        expect(parseNotificationPayload({ type: "other", content: "x" })).toBeNull();
        expect(parseNotificationPayload({ type: "notification" })).toBeNull();
        expect(parseNotificationPayload({ type: "notification", content: "" }).content).toBe("");
        expect(notificationToastMessage({ content: "" })).toBe("Новое уведомление");
        expect(notificationKind({ user_id: 1 })).toBe("personal");
        expect(notificationKind({ role: "hr" })).toBe("role");
        expect(notificationIsPersonalForUser({ user_id: "7" }, 7)).toBe(true);
        expect(notificationIsPersonalForUser({ user_id: "7" }, 8)).toBe(false);
        expect(notificationIsPersonalForUser({ role_id: 1 }, 8)).toBe(false);
        expect(notificationIsVisibleForUser({ role_id: 2 }, 8, 2)).toBe(true);
        expect(notificationIsVisibleForUser({ role_id: 2 }, 8, 4)).toBe(false);
        expect(notificationIsVisibleForUser({ user_id: "8" }, 8, 4)).toBe(true);
        expect(notificationIsVisibleForUser({ channel_id: 10 }, 8, 4)).toBe(true);
    });
});
