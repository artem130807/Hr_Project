function digitRootNine(raw) {
    const digits = String(raw || "").replace(/\D/g, "");
    if (!digits) return null;
    const sum = digits.split("").reduce((acc, ch) => acc + Number(ch), 0);
    const mod = sum % 9;
    return mod === 0 ? 9 : mod;
}

function extractDateParts(value) {
    if (value == null || value === "") return null;

    if (value instanceof Date && !Number.isNaN(value.getTime())) {
        return {
            day: String(value.getDate()),
            month: String(value.getMonth() + 1),
            year: String(value.getFullYear()),
        };
    }

    const text = String(value).trim();
    if (!text) return null;

    // DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY
    const dmy = text.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$/);
    if (dmy) {
        return { day: dmy[1], month: dmy[2], year: dmy[3] };
    }

    // YYYY-MM-DD (+ optional time tail)
    const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s].*)?$/);
    if (iso) {
        return { day: iso[3], month: iso[2], year: iso[1] };
    }

    return null;
}

export function getCandidateNumerology(dateLike) {
    const parts = extractDateParts(dateLike);
    if (!parts) return { cs: null, cm: null };

    const cs = digitRootNine(parts.day);
    const cm = digitRootNine(`${parts.day}${parts.month}${parts.year}`);
    return { cs, cm };
}
