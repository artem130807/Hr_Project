/**
 * @jest-environment jsdom
 */
import { saveElementAsPdf, pdfSafeFilePart } from "./savePdf";

const mockSave = jest.fn();
const mockAddImage = jest.fn();
const mockAddPage = jest.fn();

jest.mock("html2canvas", () => jest.fn());
jest.mock("jspdf", () => ({
    jsPDF: jest.fn(),
}));

describe("saveElementAsPdf", () => {
    beforeEach(() => {
        const html2canvas = require("html2canvas");
        const { jsPDF } = require("jspdf");
        html2canvas.mockReset();
        mockSave.mockReset();
        mockAddImage.mockReset();
        mockAddPage.mockReset();
        jsPDF.mockReset();
        jsPDF.mockImplementation(() => ({
            internal: { pageSize: { getWidth: () => 210, getHeight: () => 297 } },
            addImage: mockAddImage,
            addPage: mockAddPage,
            save: mockSave,
        }));
        HTMLCanvasElement.prototype.getContext = () => ({
            fillStyle: "",
            fillRect: jest.fn(),
            drawImage: jest.fn(),
        });
        HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,AAA";
    });

    it("sanitizes filename parts", () => {
        expect(pdfSafeFilePart("Иван / Петров")).toBe("Иван Петров");
    });

    it("throws without a root node", async () => {
        await expect(saveElementAsPdf(null, { filename: "x.pdf" })).rejects.toThrow(/Нет карточки/);
    });

    it("captures the full clone and downloads a PDF without print()", async () => {
        const html2canvas = require("html2canvas");
        html2canvas.mockResolvedValue({
            width: 800,
            height: 400,
            toDataURL: () => "data:image/png;base64,AAA",
        });

        const root = document.createElement("div");
        root.className = "psych-result-print-root";
        root.innerHTML = '<button class="psych-result-print-hide">hide</button><p>Карточка</p>';
        document.body.appendChild(root);

        const print = jest.fn();
        window.print = print;

        const out = await saveElementAsPdf(root, {
            filename: "Профиль.pdf",
            hideSelectors: [".psych-result-print-hide"],
        });

        expect(print).not.toHaveBeenCalled();
        expect(html2canvas).toHaveBeenCalled();
        const cloned = html2canvas.mock.calls[0][0];
        expect(cloned.classList.contains("pdf-export-clone")).toBe(true);
        expect(cloned.style.width).toBe("794px");
        expect(html2canvas.mock.calls[0][1]).toEqual(
            expect.objectContaining({ width: 794, windowWidth: 794 })
        );
        expect(cloned.querySelector(".psych-result-print-hide")).toBeNull();
        expect(cloned.textContent).toContain("Карточка");
        expect(mockSave).toHaveBeenCalledWith("Профиль.pdf");
        expect(mockAddPage).not.toHaveBeenCalled();
        expect(out.pages).toBe(1);
        root.remove();
    });

    it("splits a tall capture across A4 pages", async () => {
        const html2canvas = require("html2canvas");
        html2canvas.mockResolvedValue({
            width: 800,
            height: 4000,
            toDataURL: () => "data:image/png;base64,AAA",
        });
        const root = document.createElement("div");
        document.body.appendChild(root);
        await saveElementAsPdf(root, { filename: "long.pdf" });
        expect(mockAddPage).toHaveBeenCalled();
        expect(mockSave).toHaveBeenCalledWith("long.pdf");
        root.remove();
    });
});
