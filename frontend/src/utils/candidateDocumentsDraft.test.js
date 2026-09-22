import { parseCandidateDocumentsDraft } from "./candidateDocumentsDraft";

describe("candidate documents local draft", () => {
    const valid = {
        id: "draft-1",
        kind: "passport",
        filename: "passport.jpg",
        contentType: "image/jpeg",
        size: 4,
        dataUrl: "data:image/jpeg;base64,/9j/",
    };

    it("restores only valid known document entries", () => {
        const result = parseCandidateDocumentsDraft(JSON.stringify([
            valid,
            { ...valid, id: "bad-kind", kind: "malware" },
            { ...valid, id: "bad-data", dataUrl: "javascript:alert(1)" },
        ]));
        expect(result).toEqual([valid]);
    });

    it.each([null, "not-json", "{}"])("safely ignores a corrupt draft: %p", (value) => {
        expect(parseCandidateDocumentsDraft(value)).toEqual([]);
    });
});
