/**
 * @jest-environment jsdom
 */
import { printPsychResultPdf } from "./psychPdfExport";

const mockSaveElementAsPdf = jest.fn();

jest.mock("../utils/savePdf", () => ({
    pdfSafeFilePart: (value) => String(value || "документ").replace(/[\\/:*?"<>|]+/g, " ").trim(),
    saveElementAsPdf: (...args) => mockSaveElementAsPdf(...args),
}));

describe("printPsychResultPdf", () => {
    beforeEach(() => {
        mockSaveElementAsPdf.mockReset();
        mockSaveElementAsPdf.mockResolvedValue({ pages: 2 });
        window.print = jest.fn();
    });

    it("exports the psych card to a named PDF file", async () => {
        const root = document.createElement("section");
        await printPsychResultPdf({ root, fullName: "Иванов Иван", takenAt: "2026-08-24" });
        expect(window.print).not.toHaveBeenCalled();
        expect(mockSaveElementAsPdf).toHaveBeenCalledWith(
            root,
            expect.objectContaining({
                filename: expect.stringMatching(/Оценка кандидата — Иванов Иван.*\.pdf$/),
            })
        );
    });
});
