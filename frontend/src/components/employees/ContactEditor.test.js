/** @jest-environment jsdom */
import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ContactEditor from "./ContactEditor";

describe("ContactEditor", () => {
    it("renders several typed contacts and primary state", () => {
        render(<ContactEditor contacts={[
            { id: 1, contact_type: "telegram", value: "@ivan", usage_type: "work_personal", is_primary: true, is_active: true, allow_adaptation: true, verified_at: "2026-09-16" },
            { id: 2, contact_type: "email", value: "ivan@example.com", usage_type: "personal", is_primary: false, is_active: true },
        ]} onCreate={jest.fn()} onUpdate={jest.fn()} onDeactivate={jest.fn()} />);
        expect(screen.getByTestId("contact-list")).toHaveTextContent("@ivan");
        expect(screen.getByTestId("contact-list")).toHaveTextContent("основной");
        expect(screen.getByTestId("contact-list")).toHaveTextContent("ivan@example.com");
    });

    it("creates a telegram contact with adaptation permission", async () => {
        const onCreate = jest.fn(() => Promise.resolve());
        render(<ContactEditor contacts={[]} onCreate={onCreate} onUpdate={jest.fn()} onDeactivate={jest.fn()} />);
        fireEvent.change(screen.getByPlaceholderText("Значение контакта"), { target: { value: "@ivan_work" } });
        fireEvent.click(screen.getByLabelText("Разрешить использовать для адаптации"));
        fireEvent.click(screen.getByRole("button", { name: "Добавить контакт" }));
        await waitFor(() => expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ contact_type: "telegram", value: "@ivan_work", allow_adaptation: true })));
    });

    it("forces shared ownership in department mode", async () => {
        const onCreate = jest.fn(() => Promise.resolve());
        render(<ContactEditor departmentMode contacts={[]} onCreate={onCreate} onUpdate={jest.fn()} onDeactivate={jest.fn()} />);
        fireEvent.change(screen.getByPlaceholderText("Значение контакта"), { target: { value: "team@example.com" } });
        fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "email" } });
        fireEvent.click(screen.getByRole("button", { name: "Добавить контакт" }));
        await waitFor(() => expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ usage_type: "shared" })));
    });

    it("hides all mutations in read-only mode", () => {
        render(<ContactEditor readOnly contacts={[{ id: 1, contact_type: "email", value: "team@example.com", usage_type: "shared", is_active: true }]} onCreate={jest.fn()} onUpdate={jest.fn()} onDeactivate={jest.fn()} />);
        expect(screen.getByTestId("contact-list")).toHaveTextContent("team@example.com");
        expect(screen.queryByTestId("contact-form")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Отключить" })).not.toBeInTheDocument();
    });

    it("clears telegram-only flags when contact type changes", () => {
        render(<ContactEditor contacts={[]} onCreate={jest.fn()} onUpdate={jest.fn()} onDeactivate={jest.fn()} />);
        fireEvent.change(screen.getByPlaceholderText("Telegram chat ID (после подтверждения)"), { target: { value: "12345" } });
        fireEvent.click(screen.getByLabelText("Контакт подтверждён"));
        fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "email" } });
        fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "telegram" } });
        expect(screen.getByPlaceholderText("Telegram chat ID (после подтверждения)")).toHaveValue("");
        expect(screen.getByLabelText("Контакт подтверждён")).not.toBeChecked();
    });
});
