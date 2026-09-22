/** @jest-environment jsdom */
import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import RequestFormModal from "./RequestFormModal";

jest.mock("../../context/AuthContext", () => ({ useAuth: () => ({ user: null }) }));

beforeAll(() => { HTMLElement.prototype.scrollTo = jest.fn(); });
afterAll(() => { delete HTMLElement.prototype.scrollTo; });

test("anonymous applicant can enter their department", () => {
    render(<RequestFormModal publicMode closable={false} onSubmit={jest.fn()} />);
    const department = screen.getByLabelText("Подразделение *");
    fireEvent.change(department, { target: { value: "Логистика" } });
    expect(department).toHaveValue("Логистика");
});

test("authenticated request does not allow overriding the profile department", () => {
    render(<RequestFormModal onSubmit={jest.fn()} />);
    expect(screen.queryByLabelText("Подразделение *")).not.toBeInTheDocument();
});
