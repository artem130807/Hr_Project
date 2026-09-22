/**
 * @jest-environment jsdom
 */
import {
    printPsychResultPdf,
    printProfessionalResultPdf,
    printProfessionalTestPdf,
} from "./printPdf";

const mockSaveElementAsPdf = jest.fn();

jest.mock("./savePdf", () => ({
    pdfSafeFilePart: (value) =>
        String(value || "документ")
            .replace(/[\\/:*?"<>|]+/g, " ")
            .replace(/\s+/g, " ")
            .trim(),
    saveElementAsPdf: (...args) => mockSaveElementAsPdf(...args),
}));

describe("printPdf save wrappers", () => {
    beforeEach(() => {
        mockSaveElementAsPdf.mockReset();
        mockSaveElementAsPdf.mockResolvedValue({ pages: 2 });
        window.print = jest.fn();
    });

    it("saves a psych result card without print dialog", async () => {
        const root = document.createElement("div");
        await printPsychResultPdf({
            root,
            fullName: "Иванов Иван",
            takenAt: "2026-08-24",
        });
        expect(window.print).not.toHaveBeenCalled();
        expect(mockSaveElementAsPdf).toHaveBeenCalledWith(
            root,
            expect.objectContaining({
                filename: expect.stringContaining("Иванов Иван"),
            })
        );
        expect(mockSaveElementAsPdf.mock.calls[0][1].filename).toMatch(/\.pdf$/);
    });

    it("saves professional result and test cards", async () => {
        const root = document.createElement("div");
        await printProfessionalResultPdf({
            root,
            fullName: "Иванов Иван",
            testName: "Тест логиста",
            takenAt: "2026-08-24",
        });
        await printProfessionalTestPdf({ root, testName: "Тест логиста / склад" });
        expect(window.print).not.toHaveBeenCalled();
        expect(mockSaveElementAsPdf).toHaveBeenCalledTimes(2);
        expect(mockSaveElementAsPdf.mock.calls[0][1].filename).toContain("Тест логиста");
        expect(mockSaveElementAsPdf.mock.calls[1][1].filename).toContain("Тест логиста");
    });
});
