/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import AdaptationDetailPage from "./AdaptationDetailPage";

jest.mock(
    "react-router-dom",
    () => ({
        NavLink: ({ children, to }) => <a href={to}>{children}</a>,
        Link: ({ children, to }) => <a href={to}>{children}</a>,
        useNavigate: () => jest.fn(),
        useParams: () => ({ checkpointId: "4" }),
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
    getAdaptationCheckpoint: jest.fn((id) =>
        Promise.resolve(
            require("../data/mockAdaptation").MOCK_ADAPTATION_ITEMS.find((i) => String(i.id) === String(id))
        )
    ),
    submitAdaptationAnswer: jest.fn(),
}));

describe("AdaptationDetailPage", () => {
    it("loads mock checkpoint and keeps manager-safe notes", async () => {
        render(<AdaptationDetailPage />);
        expect(await screen.findByTestId("adaptation-detail-title")).toHaveTextContent("Белогубов");
        expect(screen.getByTestId("manager-safe")).toHaveTextContent("Комментарий для руководителя не заполнен.");
        expect(screen.getByTestId("manager-safe")).not.toHaveTextContent("Подтвердить испытательный срок");
        expect(screen.getByTestId("save-answers")).toBeInTheDocument();
    });
});
