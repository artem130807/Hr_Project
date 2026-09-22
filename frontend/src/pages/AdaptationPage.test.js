/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import AdaptationPage from "./AdaptationPage";
import {
    listAdaptationCheckpoints,
    getAdaptationReports,
    enrollAdaptation,
    getAdaptationSettings,
    getAdaptationNotificationTemplates,
    getAdaptationNotificationErrors,
} from "../services/adaptationApi";
import { getUsers } from "../services/userApi";
import { getHiredEmployees } from "../services/hrOpsApi";
import { MOCK_ADAPTATION_LIST } from "../data/mockAdaptation";

const mockNavigate = jest.fn();

jest.mock(
    "react-router-dom",
    () => ({
        NavLink: ({ children, to }) => <a href={to}>{children}</a>,
        useNavigate: () => mockNavigate,
        Link: ({ children, to }) => <a href={to}>{children}</a>,
    }),
    { virtual: true }
);

const mockShowAlert = jest.fn();

jest.mock("../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));

jest.mock("../context/AuthContext", () => ({
    useAuth: () => ({
        user: { id: 1, role: "hr", username: "hr" },
        logout: jest.fn(),
    }),
}));

jest.mock("../services/userApi", () => ({
    getInviteUrl: jest.fn(),
    getUsers: jest.fn(),
}));
jest.mock("../services/hrOpsApi", () => ({
    getHiredEmployees: jest.fn(),
}));
jest.mock("../services/hhAuthApi", () => ({
    checkHHAuth: jest.fn(() => Promise.resolve({ auth_passed: true })),
    getHHAuthLink: jest.fn(() => Promise.resolve("https://hh.example/auth")),
}));
jest.mock("../components/sidebar/AutoSelectSection", () => () => null);
jest.mock("../components/notifications/NotificationBell", () => () => null);

jest.mock("../services/adaptationApi", () => ({
    listAdaptationCheckpoints: jest.fn(),
    enrollAdaptation: jest.fn(),
    getAdaptationReports: jest.fn(),
    getAdaptationSettings: jest.fn(),
    updateAdaptationSettings: jest.fn(),
    getAdaptationNotificationTemplates: jest.fn(),
    updateAdaptationNotificationTemplate: jest.fn(),
    getAdaptationNotificationErrors: jest.fn(),
    retryAdaptationNotification: jest.fn(),
    getAdaptationTakeLinks: jest.fn(),
    createTemporaryAdaptation: jest.fn(),
}));

describe("AdaptationPage", () => {
    beforeEach(() => {
        mockNavigate.mockClear();
        mockShowAlert.mockClear();
        listAdaptationCheckpoints.mockResolvedValue(MOCK_ADAPTATION_LIST);
        getAdaptationReports.mockRejectedValue(new Error("offline"));
        enrollAdaptation.mockResolvedValue({
            id: 1,
            employee_id: 11,
            full_name: "Иванов ERP",
            take_links: [{
                role: "employee",
                token: "emp-token",
                path: "/adaptation/forms/emp-token",
                kind_label: "1 неделя",
                plan_date: "2026-09-16",
            }],
        });
        getAdaptationSettings.mockResolvedValue({
            overdue_enabled: true,
            overdue_time: "09:00",
            timezone: "Europe/Samara",
            show_photo: true,
        });
        getAdaptationNotificationTemplates.mockResolvedValue([
            {
                audience: "employee",
                event: "initial",
                text: "{full_name}, заполните форму «{stage}» до {plan_date}: {link}",
                enabled: true,
            },
        ]);
        getAdaptationNotificationErrors.mockResolvedValue([]);
        getUsers.mockResolvedValue([
            {
                id: "erp-1",
                erp_user_id: "erp-1",
                full_name: "Иванов ERP",
                username: "ivanov@ex.com",
                department: "Менеджер",
                position: "Менеджер",
                role: "manager",
            },
        ]);
        getHiredEmployees.mockResolvedValue([]);
    });

    it("renders prototype list from API mock", async () => {
        render(<AdaptationPage />);
        await waitFor(() => {
            expect(screen.getByRole("heading", { name: "Адаптация сотрудников" })).toBeInTheDocument();
        });
        expect(screen.getByTestId("adaptation-table")).toHaveTextContent("Касумов Александр Сергеевич");
        expect(screen.getByTestId("adaptation-table")).toHaveTextContent("Абайдуллин");
        expect(screen.getByTestId("adaptation-attention")).toHaveTextContent("Просрочен");
        expect(screen.getByText("ТЕСТЫ / АДАПТАЦИЯ")).toBeInTheDocument();
    });

    it("shows active and terminated period rows with document navigation", async () => {
        getAdaptationReports.mockResolvedValueOnce({
            internal: [{ employee: "Активный пример", position: "Логист", stage: "1 месяц", plan_date: "2026-09-10", enrollment_id: 42 }],
            terminated: [{ employee: "Уволенный пример", stage: "1 неделя", plan_date: "2026-09-05", fact_date: "2026-09-06", enrollment_id: 43 }],
            manager_safe: [],
        });
        render(<AdaptationPage />);
        fireEvent.click(await screen.findByTestId("adaptation-report"));
        const dialog = await screen.findByTestId("report-modal");
        expect(dialog).toHaveTextContent("Активный пример");
        expect(dialog).toHaveTextContent("Уволенный пример");
        expect(dialog).not.toHaveTextContent("Заключение об испытательном сроке");
        fireEvent.click(within(dialog).getAllByRole("button", { name: "Открыть" })[0]);
        expect(mockNavigate).toHaveBeenCalledWith("/tests/adaptation/case/42");
    });

    it("does not fabricate a period report when API fails", async () => {
        getAdaptationReports.mockRejectedValueOnce(new Error("Сервис недоступен"));
        render(<AdaptationPage />);
        fireEvent.click(await screen.findByTestId("adaptation-report"));
        await waitFor(() => expect(mockShowAlert).toHaveBeenCalledWith("Сервис недоступен", "error"));
        expect(screen.queryByTestId("report-modal")).not.toBeInTheDocument();
    });

    it("filters by FIO and hides completed", async () => {
        render(<AdaptationPage />);
        fireEvent.change(await screen.findByTestId("filter-search"), { target: { value: "Белогубов" } });
        const table = screen.getByTestId("adaptation-table");
        expect(table).toHaveTextContent("Белогубов");
        expect(table).not.toHaveTextContent("Касумов");
        fireEvent.change(screen.getByTestId("filter-search"), { target: { value: "" } });
        fireEvent.click(screen.getByTestId("hide-completed"));
        expect(screen.getByTestId("adaptation-table")).not.toHaveTextContent("Белогубов Андрей");
    });

    it("opens a checkpoint", async () => {
        render(<AdaptationPage />);
        const row = await screen.findByTestId("adaptation-row-1");
        fireEvent.click(within(row).getByRole("button", { name: "Открыть" }));
        expect(mockNavigate).toHaveBeenCalledWith("/tests/adaptation/1");
    });

    it("opens the employee case from FIO", async () => {
        render(<AdaptationPage />);
        fireEvent.click(await screen.findByTestId("adaptation-fio-1"));
        expect(mockNavigate).toHaveBeenCalledWith("/tests/adaptation/case/1");
    });

    it("lists ERP users in the enroll modal and department filter", async () => {
        render(<AdaptationPage />);
        fireEvent.click(await screen.findByTestId("adaptation-add"));
        expect(await screen.findByTestId("enroll-modal")).toBeInTheDocument();
        expect(await screen.findByTestId("enroll-employee")).toHaveTextContent("Иванов ERP");
        expect(await screen.findByTestId("filter-department")).toHaveTextContent("Менеджер");
        fireEvent.click(screen.getByTestId("enroll-employee-erp-1"));
        fireEvent.click(screen.getByRole("button", { name: "Поставить и получить ссылку" }));
        await waitFor(() => {
            expect(enrollAdaptation).toHaveBeenCalledWith({
                erp_user_id: "erp-1",
                route: "full",
                include_control_2m: false,
            });
        });
        expect(await screen.findByTestId("adaptation-take-links")).toHaveTextContent("Копировать ссылку");
    });

    it("loads archived adaptations separately without replacing the active contract", async () => {
        render(<AdaptationPage />);
        fireEvent.click(await screen.findByTestId("show-archived"));

        await waitFor(() => expect(listAdaptationCheckpoints).toHaveBeenLastCalledWith(
            expect.objectContaining({ archived: true })
        ));
        expect(screen.getByText("Архив адаптаций")).toBeInTheDocument();
    });

    it("shows human-readable notification settings and can cancel", async () => {
        render(<AdaptationPage />);
        fireEvent.click(await screen.findByRole("button", { name: "Настройки" }));

        const modal = await screen.findByTestId("adaptation-settings-modal");
        expect(modal).toHaveTextContent("Первое уведомление");
        expect(modal).toHaveTextContent("Сотруднику");
        expect(modal).toHaveTextContent("Иванов Иван Иванович, заполните форму «Первый месяц»");
        expect(modal).not.toHaveTextContent("employee · initial");

        fireEvent.click(screen.getByTestId("adaptation-settings-cancel"));
        expect(screen.queryByTestId("adaptation-settings-modal")).not.toBeInTheDocument();
    });
});
