import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import CandidateStatusTree from "./CandidateStatusTree";

describe("CandidateStatusTree", () => {
    it("shows Russian labels and blocks invalid transitions", () => {
        const onSelect = jest.fn();
        render(
            <CandidateStatusTree
                currentStatus="оффер принят"
                allowedTransitions={["Full documents", "отказ"]}
                onSelect={onSelect}
            />
        );

        expect(screen.getByText("Все документы")).toBeInTheDocument();
        expect(screen.queryByText("Full documents")).not.toBeInTheDocument();
        expect(screen.getByText("Тест отправлен").closest("button")).toBeDisabled();
        fireEvent.click(screen.getByText("Все документы"));
        expect(onSelect).toHaveBeenCalledWith("Full documents");
    });
});
