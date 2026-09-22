import { pdfSafeFilePart, saveElementAsPdf } from "./savePdf";
import { documentFilename } from "./documentFilename";

const HIDE = [".psych-result-print-hide", ".prof-result-print-hide", ".prof-test-print-hide"];

export function printPsychResultPdf({ fullName, position, takenAt, id, root } = {}) {
    const el = root || document.querySelector(".psych-result-print-root");
    return saveElementAsPdf(el, {
        filename: documentFilename({ type: "Оценка кандидата", fullName, position, date: takenAt, id }),
        hideSelectors: HIDE,
    });
}

export function printProfessionalResultPdf({ fullName, position, testName, takenAt, id, root } = {}) {
    const el = root || document.querySelector(".prof-result-print-root");
    return saveElementAsPdf(el, {
        filename: documentFilename({ type: "Профессиональный тест", fullName, position, stage: testName, date: takenAt, id }),
        hideSelectors: HIDE,
    });
}

export function printProfessionalTestPdf({ testName, root } = {}) {
    const el = root || document.querySelector(".prof-test-print-root");
    return saveElementAsPdf(el, {
        filename: documentFilename({ type: "Профессиональный тест", stage: pdfSafeFilePart(testName), date: null }),
        hideSelectors: HIDE,
    });
}
