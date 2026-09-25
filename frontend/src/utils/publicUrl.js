function normalizeBase(value) {
    const raw = String(value || "").trim();
    if (!raw || raw === "." || raw === "/") return "";
    try {
        const pathname = /^https?:\/\//i.test(raw) ? new URL(raw).pathname : raw;
        return `/${pathname.replace(/^\/+|\/+$/g, "")}`;
    } catch {
        return `/${raw.replace(/^\/+|\/+$/g, "")}`;
    }
}

/** Base path injected by Create React App (for example `/Hr_Project` on Pages). */
export function appBasePath() {
    return normalizeBase(process.env.PUBLIC_URL);
}

/** Return an application path that also works when hosted in a subdirectory. */
export function appPath(path = "/") {
    const base = appBasePath();
    const suffix = `/${String(path || "").replace(/^\/+/, "")}`;
    return `${base}${suffix}` || "/";
}

export function appAbsoluteUrl(path, origin = (typeof window !== "undefined" ? window.location.origin : "")) {
    return `${String(origin || "").replace(/\/$/, "")}${appPath(path)}`;
}
