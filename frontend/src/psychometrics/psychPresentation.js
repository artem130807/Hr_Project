/** Presentation policy for the public take flow. Scoring still keys by item code. */

import {
    clearPsychTakeDraft,
    getBrowserLocalStorage,
    readPsychTakeDraft,
    writePsychTakeDraft,
} from "./psychTakeDraft";

export const DEFAULT_PRESENTATION = {
    scheme: "231",
    block_order: ["avp", "sjt", "disc"],
    shuffle_modules: ["avp"],
    block_count: 3,
};

const SESSION_PREFIX = "psych-take-presentation:";

export function mulberry32(seed) {
    let state = seed >>> 0;
    return function rng() {
        state = (state + 0x6d2b79f5) >>> 0;
        let t = state;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

export function normalizePresentation(raw) {
    const data = raw && typeof raw === "object" ? raw : {};
    const block_order = (data.block_order || DEFAULT_PRESENTATION.block_order).filter(Boolean);
    const shuffle_modules = (data.shuffle_modules || DEFAULT_PRESENTATION.shuffle_modules).filter(Boolean);
    return {
        scheme: data.scheme || DEFAULT_PRESENTATION.scheme,
        block_order: block_order.length ? block_order : [...DEFAULT_PRESENTATION.block_order],
        shuffle_modules,
        block_count: block_order.length || DEFAULT_PRESENTATION.block_count,
        blocks: data.blocks,
    };
}

function shuffleCopy(list, rng) {
    const out = list.slice();
    for (let i = out.length - 1; i > 0; i -= 1) {
        const j = Math.floor(rng() * (i + 1));
        const tmp = out[i];
        out[i] = out[j];
        out[j] = tmp;
    }
    return out;
}

export function applyPsychPresentation(items, presentation, seed) {
    const spec = normalizePresentation(presentation);
    const groups = new Map();
    (items || []).forEach((item) => {
        const module = item?.module || "_";
        if (!groups.has(module)) groups.set(module, []);
        groups.get(module).push(item);
    });
    const rng = seed == null ? null : mulberry32(seed >>> 0);
    if (rng) {
        spec.shuffle_modules.forEach((module) => {
            if (groups.has(module)) {
                groups.set(module, shuffleCopy(groups.get(module), rng));
            }
        });
    }
    const out = [];
    const used = new Set();
    spec.block_order.forEach((module) => {
        if (groups.has(module)) {
            out.push(...groups.get(module));
            used.add(module);
        }
    });
    groups.forEach((bucket, module) => {
        if (!used.has(module)) out.push(...bucket);
    });
    return out;
}

export function blockNumber(module, presentation) {
    const spec = normalizePresentation(presentation);
    const idx = spec.block_order.indexOf(module);
    return idx >= 0 ? idx + 1 : spec.block_count;
}

export function sessionStorageKey(instrumentId) {
    return `${SESSION_PREFIX}${instrumentId || "unknown"}`;
}

function randomSeed() {
    const n = Math.floor(Math.random() * 0xffffffff);
    return (n >>> 0) || 1;
}

function readLegacyPresentation(instrumentId, sessionStore) {
    if (!sessionStore) return null;
    try {
        const parsed = JSON.parse(sessionStore.getItem(sessionStorageKey(instrumentId)) || "null");
        if (parsed?.seed != null && Array.isArray(parsed.codes)) return parsed;
    } catch {
        /* ignore */
    }
    return null;
}

/**
 * Build (or restore) the shuffled item order for a take.
 * Progress lives in localStorage via psychTakeDraft; sessionStorage is only a one-time migrate.
 */
export function createTakeSession(
    instrument,
    storage = getBrowserLocalStorage(),
    {
        scope = "anon",
        sessionStore = typeof sessionStorage !== "undefined" ? sessionStorage : null,
        now = Date.now(),
    } = {}
) {
    const items = instrument?.items || [];
    const presentation = normalizePresentation(instrument?.presentation);
    const itemCodes = items.map((it) => it.code);
    const draft = readPsychTakeDraft(instrument?.id, { storage, scope, itemCodes, now });
    const legacy = readLegacyPresentation(instrument?.id, sessionStore);

    const tryOrder = (seed, codes) => {
        if (seed == null || !Array.isArray(codes) || codes.length !== items.length) return null;
        const byCode = new Map(items.map((it) => [it.code, it]));
        if (!codes.every((code) => byCode.has(code))) return null;
        return {
            items: codes.map((code) => byCode.get(code)),
            seed,
            presentation,
            draft,
        };
    };

    const restored = tryOrder(draft?.seed, draft?.codes) || tryOrder(legacy?.seed, legacy?.codes);
    if (restored) {
        if (sessionStore && instrument?.id) sessionStore.removeItem(sessionStorageKey(instrument.id));
        return restored;
    }

    const seed = randomSeed();
    const presented = applyPsychPresentation(items, presentation, seed);
    writePsychTakeDraft(
        instrument?.id,
        {
            seed,
            codes: presented.map((it) => it.code),
            answers: draft?.answers || {},
            questionIndex: 0,
            fullName: draft?.fullName || "",
            position: draft?.position || "",
            birthDate: draft?.birthDate || "",
            startedAt: now,
            activeMs: 0,
            latencies: {},
        },
        { storage, scope, now }
    );
    if (sessionStore && instrument?.id) sessionStore.removeItem(sessionStorageKey(instrument.id));
    return { items: presented, seed, presentation, draft: null };
}

export function clearTakeSession(
    instrumentId,
    storage = getBrowserLocalStorage(),
    { scope = "anon", sessionStore = typeof sessionStorage !== "undefined" ? sessionStorage : null } = {}
) {
    clearPsychTakeDraft(instrumentId, { storage, scope });
    if (sessionStore) {
        try {
            sessionStore.removeItem(sessionStorageKey(instrumentId));
        } catch {
            /* ignore */
        }
    }
}
