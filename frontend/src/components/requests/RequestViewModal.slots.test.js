import { render, screen } from "@testing-library/react";
import RequestViewModal from "./RequestViewModal";

jest.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ user: { role: "hr" } }),
}));

test("shows the four request-place states and cycle number", () => {
  render(
    <RequestViewModal
      request={{
        id: 7,
        position: "Логист",
        department: "логистический",
        headcount: 4,
        status: "опубликована",
        slot_summary: { free: 1, planned: 1, adapting: 1, closed: 1 },
        slots: [
          { id: 1, ordinal: 1, status: "free", cycle: 1 },
          { id: 2, ordinal: 2, status: "adapting", cycle: 2 },
        ],
      }}
      onClose={jest.fn()}
      onStatusChange={jest.fn()}
    />
  );

  expect(screen.getByText("Места заявки")).toBeTruthy();
  expect(screen.getAllByText("Свободно").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Запланировано").length).toBeGreaterThan(0);
  expect(screen.getAllByText("На адаптации").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Закрыто").length).toBeGreaterThan(0);
  expect(screen.getByText("Место №2 · цикл 2")).toBeTruthy();
});
