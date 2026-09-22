import {
    parseVapidKeyPayload,
    shouldReplacePushSubscription,
    subscriptionToPayload,
    urlBase64ToUint8Array,
} from "./webPushLogic";

describe("webPushLogic", () => {
    it("decodes a URL-safe VAPID key", () => {
        expect(Array.from(urlBase64ToUint8Array("AQID"))).toEqual([1, 2, 3]);
    });

    it("validates VAPID payloads", () => {
        expect(parseVapidKeyPayload({ enabled: true, public_key: "key" }))
            .toEqual({ enabled: true, publicKey: "key" });
        expect(parseVapidKeyPayload({ enabled: false, public_key: "key" }).enabled).toBe(false);
    });

    it("serializes a browser subscription and detects key rotation", () => {
        const payload = subscriptionToPayload({
            toJSON: () => ({ endpoint: "https://push.example/1", keys: { p256dh: "p", auth: "a" } }),
        });
        expect(payload.endpoint).toBe("https://push.example/1");
        expect(subscriptionToPayload({ toJSON: () => ({ endpoint: "x" }) })).toBeNull();
        expect(shouldReplacePushSubscription("old", "new")).toBe(true);
        expect(shouldReplacePushSubscription("", "new")).toBe(false);
    });
});
