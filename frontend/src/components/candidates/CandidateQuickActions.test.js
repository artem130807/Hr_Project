/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { CARD_STATUS_ACTIONS } from "../../utils/candidateStatuses";
import CandidateQuickActions from "./CandidateQuickActions";

describe("CandidateQuickActions", () => {
    it("exposes interview, hold, reject and keeps offer as a separate action", () => {
        expect(CARD_STATUS_ACTIONS.map((a) => a.status)).toEqual(["собес", "подумать", "отказ"]);
        expect(typeof CandidateQuickActions).toBe("function");
    });

    it("opens interview invite instead of setting status immediately", () => {
        const onInterview = jest.fn();
        const onStatus = jest.fn();
        render(
            <CandidateQuickActions
                candidate={{ id: 1, status: "откликнулся" }}
                onInterview={onInterview}
                onStatus={onStatus}
            />
        );
        fireEvent.click(screen.getByRole("button", { name: "На собеседование" }));
        expect(onInterview).toHaveBeenCalled();
        expect(onStatus).not.toHaveBeenCalled();
    });
});

