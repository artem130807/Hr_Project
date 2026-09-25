import { appAbsoluteUrl } from "../utils/publicUrl";

export function publicAdaptationFormUrl(token, providedUrl = "") {
    const path = `/adaptation/forms/${encodeURIComponent(String(token || ""))}`;
    if (providedUrl) {
        try {
            return new URL(providedUrl, window.location.origin).toString();
        } catch (_) {
            // Fall back to the current HR frontend if backend configuration is stale.
        }
    }
    return appAbsoluteUrl(path);
}
