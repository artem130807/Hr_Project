const INVALID_FILENAME_CHARS = /[\\/:*?"<>|]+/g;

export function safeFilenamePart(value, fallback = "документ") {
    const safe = String(value || "")
        .replace(INVALID_FILENAME_CHARS, " ")
        .replace(/\s+/g, " ")
        .trim();
    return safe || fallback;
}

export function isoDatePart(value = new Date()) {
    if (!value) return "";
    const ruMatch = String(value).trim().match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (ruMatch) return `${ruMatch[3]}-${ruMatch[2]}-${ruMatch[1]}`;
    const date = value instanceof Date ? value : new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}

export function documentFilename({ type, fullName, position, stage, date, id, extension = "pdf" }) {
    const parts = [type, fullName, position, stage, isoDatePart(date), id ? `ID-${id}` : ""]
        .filter(Boolean)
        .map((part) => safeFilenamePart(part));
    return `${parts.join(" — ")}.${safeFilenamePart(extension, "pdf")}`;
}
