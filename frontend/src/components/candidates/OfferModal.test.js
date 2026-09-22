/** @jest-environment jsdom */
import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import OfferModal from "./OfferModal";

describe("OfferModal", () => {
    it("passes the explicit documents-link choice with the offer", async () => {
        const onSubmit = jest.fn(() => Promise.resolve());
        render(<OfferModal open defaultText="Текст оффера" onClose={jest.fn()} onSubmit={onSubmit} />);
        fireEvent.click(screen.getByLabelText(/Приложить ссылку для документов/i));
        fireEvent.click(screen.getByRole("button", { name: "Отправить оффер" }));
        await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("Текст оффера", true));
    });
});
