/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import EmployeeDetailPage from "./EmployeeDetailPage";

jest.mock(
    "react-router-dom",
    () => ({
        Link: ({ children }) => <span>{children}</span>,
        useParams: () => ({ employeeId: "17" }),
    }),
    { virtual: true }
);
jest.mock("../layout/MainLayout", () => ({ children }) => <main>{children}</main>);
jest.mock("../components/employees/ContactEditor", () => () => <div>Контакты</div>);
const mockShowAlert = jest.fn();
jest.mock("../context/AlertContext", () => ({ useAlertContext: () => ({ showAlert: mockShowAlert }) }));
jest.mock("../context/AuthContext", () => ({ useAuth: () => ({ user: { role: "hr" } }) }));
jest.mock("../services/hrOpsApi", () => ({
    getEmployee: jest.fn(),
    getEmployeeContacts: jest.fn(),
    updateEmployee: jest.fn(),
    createEmployeeContact: jest.fn(),
    updateContact: jest.fn(),
    deactivateContact: jest.fn(),
}));

const { getEmployee, getEmployeeContacts, updateEmployee } = require("../services/hrOpsApi");

describe("EmployeeDetailPage work start date", () => {
    beforeEach(() => {
        getEmployee.mockResolvedValue({
            id: 17,
            full_name: "Иванов Иван",
            position: "Логист",
            department: "Логистика",
            date_hired: "2026-09-01",
        });
        getEmployeeContacts.mockResolvedValue([]);
        updateEmployee.mockResolvedValue({
            id: 17,
            full_name: "Иванов Иван",
            position: "Логист",
            department: "Логистика",
            date_hired: "2026-09-15",
        });
    });

    it("allows HR to update the work start date", async () => {
        render(<EmployeeDetailPage />);

        const input = await screen.findByTestId("employee-work-start-date");
        expect(input).toHaveValue("2026-09-01");
        fireEvent.change(input, { target: { value: "2026-09-15" } });
        fireEvent.click(screen.getByTestId("save-employee-work-start-date"));

        await waitFor(() => expect(updateEmployee).toHaveBeenCalledWith("17", {
            date_hired: "2026-09-15",
        }));
        await waitFor(() => expect(input).toHaveValue("2026-09-15"));
    });
});
