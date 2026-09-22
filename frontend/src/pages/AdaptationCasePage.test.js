/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdaptationCasePage from "./AdaptationCasePage";
import { getAdaptationEnrollment, addAdaptationCheckpoint } from "../services/adaptationApi";

const mockNavigate = jest.fn();

jest.mock(
    "react-router-dom",
    () => ({
        NavLink: ({ children, to }) => <a href={to}>{children}</a>,
        Link: ({ children, to }) => <a href={to}>{children}</a>,
        useNavigate: () => mockNavigate,
        useParams: () => ({ enrollmentId: "4" }),
    }),
    { virtual: true }
);

jest.mock("../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../context/AuthContext", () => ({
    useAuth: () => ({
        user: { id: 1, role: "hr", username: "hr" },
        logout: jest.fn(),
    }),
}));

jest.mock("../services/userApi", () => ({ getInviteUrl: jest.fn() }));
jest.mock("../services/hhAuthApi", () => ({
    checkHHAuth: jest.fn(() => Promise.resolve({ auth_passed: true })),
    getHHAuthLink: jest.fn(() => Promise.resolve("https://hh.example/auth")),
}));
jest.mock("../components/sidebar/AutoSelectSection", () => () => null);
jest.mock("../components/notifications/NotificationBell", () => () => null);

jest.mock("../services/adaptationApi", () => ({
    getAdaptationEnrollment: jest.fn(() =>
        Promise.resolve({
            enrollment_id: 4,
            full_name: "Белогубов Андрей Витальевич",
            position: "Инженер-разработчик",
            department: "IT",
            date_hired: "2026-06-20",
            checkpoints: [
                { id: 4, kind: "month_2", kind_label: "2 месяца", plan_date: "2026-08-20", status: "completed", status_label: "Завершен" },
            ],
            core_series: {
                core_e1: [{ kind: "month_2", plan_date: "2026-08-20", value: 5 }],
                core_e2: [],
                core_e3: [],
                core_e4: [],
                core_e5: [],
            },
        })
    ),
    addAdaptationCheckpoint: jest.fn(),
    getAdaptationTakeLinks: jest.fn(),
}));

describe("AdaptationCasePage", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        getAdaptationEnrollment.mockResolvedValue({
            enrollment_id: 4,
            full_name: "Белогубов Андрей Витальевич",
            position: "Инженер-разработчик",
            department: "IT",
            date_hired: "2026-06-20",
            checkpoints: [
                { id: 4, kind: "month_2", kind_label: "2 месяца", plan_date: "2026-08-20", status: "completed", status_label: "Завершен" },
            ],
            core_series: {
                core_e1: [{ kind: "month_2", plan_date: "2026-08-20", value: 5 }],
                core_e2: [],
                core_e3: [],
                core_e4: [],
                core_e5: [],
            },
        });
    });

    it("shows timeline and core dynamics", async () => {
        render(<AdaptationCasePage />);
        expect(await screen.findByTestId("adaptation-case-title")).toHaveTextContent("Белогубов");
        expect(screen.getByTestId("adaptation-timeline")).toHaveTextContent("2 месяца");
        expect(screen.getByTestId("core-series")).toHaveTextContent("Комфорт");
        fireEvent.click(screen.getByRole("button", { name: "Открыть" }));
        expect(mockNavigate).toHaveBeenCalledWith("/tests/adaptation/4");
    });

    it("submits a finite weekly series with a retry key", async () => {
        render(<AdaptationCasePage />);
        await screen.findByTestId("adaptation-case-title");
        fireEvent.change(screen.getByLabelText("Повторение"), { target: { value: "weekly" } });
        fireEvent.change(screen.getByLabelText("Количество точек"), { target: { value: "3" } });
        fireEvent.change(screen.getByLabelText("Дополнительная точка"), { target: { value: "2026-09-10" } });
        fireEvent.click(screen.getByLabelText("Добавить комментарий HR"));
        fireEvent.click(screen.getByRole("button", { name: "Добавить опрос" }));
        await waitFor(() => expect(addAdaptationCheckpoint).toHaveBeenCalledWith(expect.objectContaining({
            frequency: "weekly", repeat_count: 3, plan_date: "2026-09-10", series_key: expect.any(String), include_hr: true,
            interval_days: null,
        })));
    });

    it("submits a custom recurring interval", async () => {
        render(<AdaptationCasePage />);
        await screen.findByTestId("adaptation-case-title");
        fireEvent.change(screen.getByLabelText("Повторение"), { target: { value: "custom" } });
        fireEvent.change(screen.getByLabelText("Количество точек"), { target: { value: "5" } });
        fireEvent.change(screen.getByLabelText("Интервал, дней"), { target: { value: "10" } });
        fireEvent.change(screen.getByLabelText("Дополнительная точка"), { target: { value: "2026-09-10" } });
        fireEvent.click(screen.getByRole("button", { name: "Добавить опрос" }));
        await waitFor(() => expect(addAdaptationCheckpoint).toHaveBeenCalledWith(expect.objectContaining({
            frequency: "custom", repeat_count: 5, interval_days: 10,
        })));
    });
});
