export function formatDateRu(value, fallback = "—") {
    if (value == null || value === "") return fallback;
    const raw = String(value).trim();
    if (!raw) return fallback;

    // YYYY-MM-DD
    const isoDate = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (isoDate) {
        const [, y, m, d] = isoDate;
        return `${d}.${m}.${y}`;
    }

    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return raw;

    return parsed.toLocaleDateString("ru-RU");
}

export function replaceIsoDatesInText(text) {
    if (text == null) return text;
    return String(text).replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, (_, y, m, d) => `${d}.${m}.${y}`);
}
