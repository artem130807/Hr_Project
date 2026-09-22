/** Normalize and match phone numbers for exact-style HR call search. */

export function digitsOnly(value) {
    return String(value || "").replace(/\D/g, "");
}

export function canonicalRuPhone(value) {
    let digits = digitsOnly(value);
    if (digits.length === 11 && digits.startsWith("8")) {
        digits = `7${digits.slice(1)}`;
    } else if (digits.length === 10) {
        digits = `7${digits}`;
    }
    return digits;
}

export function formatRuPhone(value) {
    const digits = canonicalRuPhone(value);
    if (digits.length !== 11 || !digits.startsWith("7")) {
        return String(value || "").trim() || "—";
    }
    return `+7 ${digits.slice(1, 4)} ${digits.slice(4, 7)}-${digits.slice(7, 9)}-${digits.slice(9, 11)}`;
}

/**
 * Concrete phone lookup: 10–11 digits → exact canonical match.
 * 4–9 digits → suffix/contains on the stored number (still number-only, not FIO).
 */
export function phoneMatches(storedPhone, query) {
    const needle = canonicalRuPhone(query);
    const haystack = canonicalRuPhone(storedPhone);
    if (!needle || needle.length < 4) return false;
    if (needle.length >= 10) {
        return haystack === needle;
    }
    return haystack.endsWith(needle) || haystack.includes(needle);
}

export function isPhoneQuery(query) {
    return canonicalRuPhone(query).length >= 4;
}

/** Both HR spellings of the company line; they canonicalize to the same 11 digits. */
export const CALL_LIST_ALLOWED_PHONES = ["+7 902 001 37 28", "+7 902 001 3728"];

export function allowedPhoneSet(phones = CALL_LIST_ALLOWED_PHONES) {
    return new Set(
        (Array.isArray(phones) ? phones : [])
            .map((value) => canonicalRuPhone(value))
            .filter((digits) => digits.length >= 10)
    );
}

export function callInvolvesAllowedPhones(call, phones = CALL_LIST_ALLOWED_PHONES) {
    const allowed = allowedPhoneSet(phones);
    if (allowed.size === 0) return true;
    return (
        allowed.has(canonicalRuPhone(call?.phone)) ||
        allowed.has(canonicalRuPhone(call?.operatorPhone))
    );
}
