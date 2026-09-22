/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import InterviewInviteModal from "./InterviewInviteModal";

jest.mock("../../context/AuthContext", () => ({
    useAuth: () => ({ user: { name: "Кудряшова Светлана Алексеевна" } }),
}));

describe("InterviewInviteModal", () => {
    it("prefills interview letter and submits date/time", async () => {
        const onSubmit = jest.fn().mockResolvedValue();
        render(
            <InterviewInviteModal
                open
                candidate={{ id: 5, full_name: "Иванов Артём Валерьевич" }}
                defaultDate="2026-07-09"
                defaultTime="16:00"
                onClose={jest.fn()}
                onSubmit={onSubmit}
            />
        );

        expect(screen.getByTestId("interview-letter").value).toContain("Артём Валерьевич, здравствуйте!");
        expect(screen.getByTestId("interview-letter").value).toContain("9 июля в 16:00");
        fireEvent.click(screen.getByTestId("interview-send"));
        await waitFor(() => expect(onSubmit).toHaveBeenCalled());
        expect(onSubmit.mock.calls[0][1]).toEqual(
            expect.objectContaining({ date: "2026-07-09", startTime: "16:00", endTime: "17:00" })
        );
        expect(onSubmit.mock.calls[0][2]).toBeNull();
    });

    it("asks to schedule a candidate reminder and passes datetime", async () => {
        const onSubmit = jest.fn().mockResolvedValue();
        render(
            <InterviewInviteModal
                open
                candidate={{ id: 5, full_name: "Иванов Артём Валерьевич" }}
                defaultDate="2026-07-09"
                defaultTime="16:00"
                onClose={jest.fn()}
                onSubmit={onSubmit}
            />
        );
        fireEvent.click(screen.getByTestId("candidate-reminder-toggle"));
        expect(screen.getByTestId("candidate-reminder-at").value).toMatch(/^2026-07-09T15:00/);
        expect(screen.getByTestId("candidate-reminder-text").value).toContain("Напоминаем о собеседовании");
        const dialog = screen.getByTestId("interview-invite-dialog");
        const body = screen.getByTestId("interview-invite-body");
        expect(dialog.className).toMatch(/max-h-\[calc\(100vh-2rem\)\]/);
        expect(dialog.className).toMatch(/flex-col/);
        expect(body.className).toMatch(/overflow-y-auto/);
        expect(body.contains(screen.getByTestId("interview-send"))).toBe(false);
        fireEvent.click(screen.getByTestId("interview-send"));
        await waitFor(() => expect(onSubmit).toHaveBeenCalled());
        expect(onSubmit.mock.calls[0][2]).toEqual(
            expect.objectContaining({
                enabled: true,
                remind_at: "2026-07-09T15:00:00",
            })
        );
    });
});
