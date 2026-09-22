/**
 * @jest-environment node
 */
import { mapCallConversation, mapCallConversations } from "./callConversationView";

describe("mapCallConversation", () => {
    it("maps ATS payload into the calls UI shape", () => {
        const view = mapCallConversation({
            id: 123,
            filename: "recording_2025-08-25_14-30-15.mp3",
            description: null,
            callStartTime: "2025-08-25T14:30:15+03:00",
            callerNumber: "+79001234567",
            operatorNumber: "+79007654321",
            duration: 327,
            status: "pending",
            direction: "incoming",
            turns: [{ at: "00:00", speaker: "hr", text: "информируем что" }],
        });
        expect(view.id).toBe(123);
        expect(view.phone).toBe("+79001234567");
        expect(view.operatorPhone).toBe("+79007654321");
        expect(view.outcome).toBe("pending");
        expect(view.summary).toContain("определяется");
        expect(view.turns[0].text).toContain("информируем");
    });

    it("accepts snake_case aliases and wrapped lists", () => {
        const view = mapCallConversation({
            id: 1,
            filename: "x.mp3",
            caller_number: "+79001112233",
            operator_number: "+79007654321",
            call_start_time: "2025-08-25T14:30:15+03:00",
            status: "no_answer",
            direction: "outgoing",
            caller_name: "Иван",
            description: "Сброс",
            ats_status: "CANCELLED_BY_CALLER",
        });
        expect(view.contactName).toBe("Иван");
        expect(view.outcome).toBe("dropped");
        expect(view.direction).toBe("outgoing");
        expect(view.summary).toBe("Сброс");
        expect(view.atsStatus).toBe("CANCELLED_BY_CALLER");
        expect(mapCallConversations({ items: [{ id: 2, filename: "b.mp3" }] })).toHaveLength(1);
        expect(mapCallConversations([null, { id: 3, filename: "c.mp3" }]).map((c) => c.id)).toEqual([3]);
        expect(mapCallConversation(null)).toBeNull();
    });
});
