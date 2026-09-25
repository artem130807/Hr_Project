/** Copy and mapping for HR psychological profile report. */

export const AVP_FACTOR_TIPS = {
    E: "Объединяет энтузиазм и ассертивность: социальную энергию, активное включение и готовность проявлять инициативу.",
    A: "Объединяет сострадание и вежливость: ориентацию на сотрудничество, уважение и учет интересов других.",
    C: "Объединяет трудолюбие и прилежность: усилия, организацию работы, надежность и доведение задач до завершения.",
    ES: "Показывает устойчивость эмоционального состояния и способность сохранять рабочую собранность при напряжении.",
    O: "Объединяет интеллектуальную вовлеченность и открытость опыту: интерес к сложным идеям, обучению и нестандартным решениям.",
};

export const BEHAVIOR_META = {
    D: {
        name: "решительность",
        tip: "Решительность, прямота и контроль результата.",
        headerTip: "Показывает прямоту, скорость принятия решений и склонность брать контроль ситуации на себя.",
        color: "var(--blue, #3b66f0)",
    },
    I: {
        name: "влияние",
        tip: "Влияние, контактность и социальная энергия.",
        headerTip: "Отражает контактность, вовлечение окружающих и социальную энергию в работе.",
        color: "var(--cyan, #11b8d7)",
    },
    S: {
        name: "стабильность",
        tip: "Стабильность темпа, терпение и поддержка.",
        headerTip: "Отражает спокойный темп, терпение и ориентацию на поддержку.",
        color: "var(--yellow, #4f46e5)",
    },
    C: {
        name: "точность",
        tip: "Точность, правила и контроль качества.",
        headerTip: "Отражает внимание к правилам, качеству и аккуратности исполнения.",
        color: "var(--green, #55a44e)",
    },
};

export const MANAGEMENT_FOCUS_TIPS = {
    P: "Ориентация на конкретный результат здесь и сейчас.",
    A: "Ориентация на порядок, правила, стабильность процессов и качество исполнения.",
    E: "Ориентация на возможности, изменения и новые способы решения задач.",
    I: "Ориентация на согласование интересов, взаимодействие и устойчивость команды.",
};

export const MANAGEMENT_FOCUS_NAMES = {
    P: "результат",
    A: "порядок и процессы",
    E: "изменения и возможности",
    I: "взаимодействие и команда",
};

export const DISC_CONTEXTS = [
    { key: "В работе", title: "В работе" },
    { key: "Под давлением", title: "Под давлением" },
    { key: "Личное", title: "Личное" },
];

export const FACTOR_NAMES = {
    E: "Экстраверсия",
    A: "Доброжелательность",
    C: "Добросовестность",
    ES: "Эмоциональная стабильность",
    O: "Интеллектуальная вовлечённость",
};

export const FACTOR_ORDER = ["E", "A", "C", "ES", "O"];
export const DISC_ORDER = ["D", "I", "S", "C"];
export const PAEI_ORDER = ["P", "A", "E", "I"];
export const PAEI_MAX = 24;
export const PAEI_GUIDE = 6;
export const DISC_RAW_MAX = 8;
export const DISC_BAR_PX = 84;

export function indexToSigned(index0to100) {
    if (index0to100 == null || Number.isNaN(Number(index0to100))) return null;
    return Math.round((Number(index0to100) - 50) * 2);
}

export function signedLevel(signed) {
    if (signed == null) return "—";
    if (signed >= 68) return "Выражено в положительном направлении";
    if (signed >= 32) return "Умеренно выражено в положительном направлении";
    if (signed <= -68) return "Выражено в отрицательном направлении";
    if (signed <= -32) return "Умеренно выражено в отрицательном направлении";
    return "Близко к центру шкалы";
}

export function formatSigned(signed) {
    if (signed == null) return "—";
    if (signed > 0) return `+${signed}`;
    return String(signed);
}

export function formatMinutes(sec) {
    if (sec == null || Number.isNaN(Number(sec))) return "—";
    const minutes = Math.max(0, Math.round(Number(sec) / 60));
    const mod10 = minutes % 10;
    const mod100 = minutes % 100;
    let word = "минут";
    if (mod100 < 11 || mod100 > 14) {
        if (mod10 === 1) word = "минута";
        else if (mod10 >= 2 && mod10 <= 4) word = "минуты";
    }
    return `${minutes} ${word}`;
}

export function qualityTone(status) {
    if (!status) return "neutral";
    if (String(status).includes("Приемлемый")) return "good";
    if (String(status).includes("Критич") || String(status).includes("Недостаточно")) return "bad";
    return "warn";
}

function byAbsSigned(a, b) {
    return Math.abs(b.signed || 0) - Math.abs(a.signed || 0);
}

export function discLeaders(rows) {
    const ranked = [...(rows || [])]
        .filter((r) => r.raw != null)
        .sort((a, b) => Number(b.raw) - Number(a.raw));
    if (!ranked.length) return { lead: null, second: null };
    return { lead: ranked[0], second: ranked[1] || null };
}

export function discCaption(rows) {
    const { lead, second } = discLeaders(rows);
    if (!lead) return "Шкала −8…+8";
    if (second && Number(second.raw) > 0) {
        return `Чаще проявляется «${lead.name}», дополнительно — «${second.name}» · шкала −8…+8`;
    }
    return `Чаще проявляется «${lead.name}» · шкала −8…+8`;
}

export function sjtQualityCopy(index) {
    if (index == null) {
        return { title: "Нет оценки", text: "Недостаточно ответов, чтобы оценить качество управленческих решений." };
    }
    if (index >= 75) {
        return {
            title: "75–100 по экспертному ключу",
            text: "Большинство выбранных вариантов совпадает с экспертным ключом рабочих ситуаций.",
        };
    }
    if (index >= 50) {
        return {
            title: "50–74 по экспертному ключу",
            text: "Часть выбранных вариантов совпадает с экспертным ключом. Приоритеты стоит уточнить на интервью.",
        };
    }
    return {
        title: "Менее 50 по экспертному ключу",
        text: "Небольшая часть выбранных вариантов совпадает с экспертным ключом. Рабочие ситуации стоит обсудить на интервью.",
    };
}

export function buildInsight({ factors, aspects, disc, paei }) {
    const topFactor = [...(factors || [])].filter((f) => f.signed != null).sort(byAbsSigned)[0];
    const work = discLeaders(disc?.["В работе"]);
    const pressure = discLeaders(disc?.["Под давлением"]);
    const topPaei = [...(paei || [])].filter((p) => p.count != null).sort((a, b) => b.count - a.count)[0];
    const topAspect = [...(aspects || [])].filter((a) => a.signed != null).sort(byAbsSigned)[0];

    const parts = [];
    if (topFactor) {
        const dir = topFactor.signed >= 32 ? "выражен" : topFactor.signed <= -32 ? "сдержан" : "умерен";
        parts.push(`${topFactor.name}: профиль ${dir} (${formatSigned(topFactor.signed)}).`);
    }
    if (work.lead) {
        parts.push(`В пилотном поведенческом блоке в обычной работе чаще проявляется «${work.lead.name}» (${formatSigned(work.lead.raw)}).`);
    }
    if (pressure.lead && work.lead && pressure.lead.code !== work.lead.code) {
        parts.push(`Под давлением заметнее «${pressure.lead.name}» (${formatSigned(pressure.lead.raw)}).`);
    } else if (pressure.lead && work.lead && Number(pressure.lead.raw) > Number(work.lead.raw)) {
        parts.push(`Под давлением та же поведенческая тенденция «${pressure.lead.name}» проявляется сильнее.`);
    }
    if (topPaei) {
        parts.push(`Во внутреннем пилотном SJT чаще выбирались решения с фокусом «${topPaei.short}».`);
    }
    const text = parts.join(" ") || "Недостаточно данных для ключевого вывода.";

    const tags = [];
    if (topAspect) tags.push(`${topAspect.name} ${formatSigned(topAspect.signed)}`);
    if (pressure.lead) tags.push(`${pressure.lead.name} под давлением ${formatSigned(pressure.lead.raw)}`);
    const labor = (aspects || []).find((a) => a.code === "Ci");
    if (labor?.signed != null) tags.push(`Трудолюбие ${formatSigned(labor.signed)}`);
    const open = (aspects || []).find((a) => a.code === "Oo");
    if (open?.signed != null) tags.push(`Открытость ${formatSigned(open.signed)}`);
    return { text, tags: tags.slice(0, 4) };
}

export function toPsychReportModel(result) {
    const scores = result?.scores || {};
    const avp = scores.avp || {};
    const factors = FACTOR_ORDER.map((code) => {
        const row = (avp.factors || []).find((f) => f.code === code) || {};
        const signed = indexToSigned(row.score);
        return {
            code,
            name: FACTOR_NAMES[code] || row.name || code,
            signed,
            level: signedLevel(signed),
            tip: AVP_FACTOR_TIPS[code] || "",
        };
    });
    const aspects = (avp.aspects || []).map((row) => ({
        ...row,
        name: row.code === "Oi" ? "Интеллектуальная вовлечённость" : row.name,
        signed: indexToSigned(row.score),
    }));
    const disc = {};
    DISC_CONTEXTS.forEach(({ key }) => {
        const behaviorScores = scores.behavior_preferences || scores.disc;
        const rows = Array.isArray(behaviorScores) ? behaviorScores : behaviorScores?.[key] || [];
        disc[key] = DISC_ORDER.map((code) => {
            const row = (rows || []).find((r) => r.code === code) || {};
            const raw = row.raw != null ? Number(row.raw) : null;
            return {
                code,
                raw,
                px: raw == null ? 0 : Math.round((Math.abs(raw) / DISC_RAW_MAX) * DISC_BAR_PX),
                positive: raw != null && raw >= 0,
                ...BEHAVIOR_META[code],
            };
        });
    });
    const paei = PAEI_ORDER.map((code) => {
        const rows = scores.management_focus_distribution || scores.paei || [];
        const row = rows.find((p) => p.code === code) || {};
        const count = row.count != null ? Number(row.count) : null;
        return {
            code,
            name: MANAGEMENT_FOCUS_NAMES[code],
            count,
            widthPct: count == null ? 0 : Math.min(100, (count / PAEI_MAX) * 100),
            tip: MANAGEMENT_FOCUS_TIPS[code],
            short: MANAGEMENT_FOCUS_NAMES[code],
        };
    });
    const qualityIndex = scores.sjt?.quality_index != null
        ? Math.round(Number(scores.sjt.quality_index))
        : null;
    const workLead = discLeaders(disc["В работе"]);
    const paeiLead = [...paei].filter((p) => p.count != null).sort((a, b) => b.count - a.count)[0];
    const insight = buildInsight({ factors, aspects, disc, paei });
    const status = result.quality_status || scores.quality?.status || scores.summary?.quality_status;

    const numerology = scores.numerology || {};
    const chs = result.chs ?? numerology.chs;
    const chm = result.chm ?? numerology.chm;
    const birthDate = result.birth_date || numerology.birth_date;

    return {
        fullName: result.full_name || "Кандидат",
        position: result.position || "",
        takenAt: result.taken_at
            ? new Date(result.taken_at).toLocaleDateString("ru-RU")
            : "—",
        birthDate: birthDate ? new Date(birthDate).toLocaleDateString("ru-RU") : "—",
        chs: chs == null || chs === "" ? "—" : chs,
        chm: chm == null || chm === "" ? "—" : chm,
        qualityStatus: status || "—",
        qualityTone: qualityTone(status),
        activeTime: formatMinutes(scores.quality?.active_duration_sec),
        behaviorPreference: workLead.lead
            ? { code: workLead.lead.code, label: BEHAVIOR_META[workLead.lead.code]?.name, tip: BEHAVIOR_META[workLead.lead.code]?.headerTip }
            : null,
        managementFocus: paeiLead
            ? { code: paeiLead.code, label: paeiLead.short, tip: MANAGEMENT_FOCUS_TIPS[paeiLead.code] }
            : null,
        factors,
        disc,
        paei,
        qualityIndex,
        sjtCopy: sjtQualityCopy(qualityIndex),
        insight,
    };
}
