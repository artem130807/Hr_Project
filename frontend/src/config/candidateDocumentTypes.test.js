import { CANDIDATE_DOCUMENT_LABELS, CANDIDATE_DOCUMENT_TYPES } from "./candidateDocumentTypes";

describe("candidate employment document catalog", () => {
    it("contains the agreed employment checklist", () => {
        expect(CANDIDATE_DOCUMENT_TYPES.map((item) => item.value)).toEqual([
            "passport",
            "snils",
            "inn",
            "marriage_certificate",
            "children_birth_certificate",
            "education",
            "employment_book",
            "military",
            "tachograph_card",
            "driver_license",
            "criminal_record_certificate",
            "medical_book",
            "other",
        ]);
        expect(CANDIDATE_DOCUMENT_LABELS.criminal_record_certificate).toMatch(/судимости/i);
        expect(CANDIDATE_DOCUMENT_LABELS.medical_book).toMatch(/санитарная/i);
    });
});
