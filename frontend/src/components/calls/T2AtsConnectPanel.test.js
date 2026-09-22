/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import T2AtsConnectPanel from "./T2AtsConnectPanel";
import { getT2OAuthTokens, putT2OAuthTokens } from "../../services/t2AuthApi";

jest.mock("../../context/AlertContext", () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

jest.mock("../../services/t2AuthApi", () => ({
    getT2OAuthTokens: jest.fn(),
    putT2OAuthTokens: jest.fn(),
    deleteT2OAuthTokens: jest.fn(),
    isT2AtsConnected: (data) => Boolean(data?.payload?.access_token && data?.payload?.refresh_token),
}));

describe("T2AtsConnectPanel", () => {
    beforeEach(() => {
        getT2OAuthTokens.mockResolvedValue({ payload: null });
        putT2OAuthTokens.mockResolvedValue({ payload: { access_token: "a", refresh_token: "r" } });
    });

    it("saves pasted ATS tokens", async () => {
        render(<T2AtsConnectPanel />);
        await waitFor(() => {
            expect(screen.getByTestId("t2-ats-status")).toHaveTextContent("Вставьте пару токенов");
        });
        fireEvent.click(screen.getByTestId("t2-ats-toggle"));
        fireEvent.change(screen.getByTestId("t2-access-token"), { target: { value: "ACCESS" } });
        fireEvent.change(screen.getByTestId("t2-refresh-token"), { target: { value: "REFRESH" } });
        fireEvent.click(screen.getByTestId("t2-ats-save"));
        await waitFor(() => {
            expect(putT2OAuthTokens).toHaveBeenCalledWith({
                access_token: "ACCESS",
                refresh_token: "REFRESH",
            });
        });
    });
});
