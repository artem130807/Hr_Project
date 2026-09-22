import {
    DISC_CONTEXTS,
    discCaption,
    formatSigned,
} from "../../psychometrics/psychReportViewModel";
import styles from "./psychResultPdf.module.css";

function signedBarStyle(signed, max) {
    if (signed == null || signed === 0) {
        return { left: "50%", width: "2px", background: "#98a2b3" };
    }
    const pct = Math.min(50, (Math.abs(signed) / max) * 50);
    if (signed > 0) {
        return {
            left: "50%",
            width: `${pct}%`,
            background: signed >= max * 0.68 ? "#11b8d7" : "#3b66f0",
        };
    }
    return { left: `${50 - pct}%`, width: `${pct}%`, background: "#3b66f0" };
}

function toneClass(tone) {
    if (tone === "good") return styles.good;
    if (tone === "bad") return styles.bad;
    if (tone === "warn") return styles.warn;
    return "";
}

function hexColor(value) {
    const match = String(value || "").match(/#([0-9a-f]{6})/i);
    return match ? `#${match[1]}` : "#3b66f0";
}

export default function PsychResultPdfDocument({ model }) {
    const donutPct = model.qualityIndex == null ? 0 : Math.max(0, Math.min(100, model.qualityIndex));

    return (
        <article className={`${styles.doc} psych-pdf-document`} data-testid="psych-pdf-document">
            <header className={styles.banner}>
                <p className={styles.kicker}>Отчёт по результатам оценки кандидата</p>
                <h1 className={styles.title}>{model.fullName}</h1>
                <p className={styles.meta}>
                    {[model.position, model.takenAt, model.birthDate && model.birthDate !== "—" ? `др ${model.birthDate}` : null]
                        .filter(Boolean)
                        .join(" · ")}
                </p>
            </header>

            <div className={styles.body}>
                <div className={styles.kpis}>
                    <div className={styles.kpi}>
                        <span className={styles.kpiLabel}>Качество</span>
                        <span className={`${styles.kpiValue} ${toneClass(model.qualityTone)}`}>
                            {model.qualityStatus}
                        </span>
                    </div>
                    <div className={styles.kpi}>
                        <span className={styles.kpiLabel}>Активное время</span>
                        <span className={styles.kpiValue}>{model.activeTime}</span>
                    </div>
                    <div className={styles.kpi}>
                        <span className={styles.kpiLabel}>ЧС / ЧМ</span>
                        <span className={styles.kpiValue}>
                            {model.chs} / {model.chm}
                        </span>
                    </div>
                    <div className={styles.kpi}>
                        <span className={styles.kpiLabel}>Поведенческая тенденция · пилот</span>
                        <span className={styles.kpiValue}>
                            {model.behaviorPreference
                                ? model.behaviorPreference.label
                                : "—"}
                        </span>
                    </div>
                    <div className={styles.kpi}>
                        <span className={styles.kpiLabel}>Фокус решений · пилотный SJT</span>
                        <span className={styles.kpiValue}>
                            {model.managementFocus
                                ? model.managementFocus.label
                                : "—"}
                        </span>
                    </div>
                    <div className={styles.kpi}>
                        <span className={styles.kpiLabel}>Соответствие экспертному ключу</span>
                        <span className={styles.kpiValue}>
                            {model.qualityIndex == null ? "—" : `${model.qualityIndex} из 100`}
                        </span>
                    </div>
                </div>

                <section className={styles.section}>
                    <h2 className={styles.sectionTitle}>Пять факторов BFAS</h2>
                    <div className={styles.card}>
                        {model.factors.map((row) => (
                            <div className={styles.factor} key={row.code}>
                                <div className={styles.factorHead}>
                                    <span className={styles.factorName}>{row.name}</span>
                                    <span className={styles.factorScore}>
                                        {formatSigned(row.signed)} · {row.level}
                                    </span>
                                </div>
                                <div className={styles.track}>
                                    <span className={styles.mid} />
                                    <span className={styles.fill} style={signedBarStyle(row.signed, 100)} />
                                </div>
                                {row.tip ? <p className={styles.hint}>{row.tip}</p> : null}
                            </div>
                        ))}
                        <div className={styles.axis}>
                            <span>−100</span>
                            <span>−68</span>
                            <span>0</span>
                            <span>+68</span>
                            <span>+100</span>
                        </div>
                    </div>
                    <div className={styles.callout}>
                        <h2>Наблюдения для интервью</h2>
                        <p>{model.insight.text}</p>
                        {model.behaviorPreference?.tip ? <p className={styles.hint}>{model.behaviorPreference.tip}</p> : null}
                        {model.managementFocus?.tip ? <p className={styles.hint}>{model.managementFocus.tip}</p> : null}
                        <div className={styles.tags}>
                            {model.insight.tags.map((tag) => (
                                <span className={styles.tag} key={tag}>
                                    {tag}
                                </span>
                            ))}
                        </div>
                    </div>
                </section>

                <section className={styles.section}>
                    <h2 className={styles.sectionTitle}>Рабочие предпочтения — внутренний пилотный поведенческий блок</h2>
                    <div className={styles.card}>
                        {DISC_CONTEXTS.map((ctx) => {
                            const rows = model.disc[ctx.key] || [];
                            return (
                                <div className={styles.discBlock} key={ctx.key}>
                                    <div className={styles.discHead}>
                                        <h3>{ctx.title}</h3>
                                        <p className={styles.caption}>{discCaption(rows)}</p>
                                    </div>
                                    {rows.map((col) => (
                                        <div key={col.code}>
                                            <div className={styles.discRow}>
                                                <span className={styles.code}>{col.name.slice(0, 1).toUpperCase()}</span>
                                                <div className={`${styles.track} ${styles.plainTrack}`}>
                                                    <span className={styles.mid} />
                                                    <span
                                                        className={styles.fill}
                                                        style={{
                                                            ...signedBarStyle(col.raw, 8),
                                                            background: hexColor(col.color),
                                                        }}
                                                    />
                                                </div>
                                                <span className={styles.val}>{formatSigned(col.raw)}</span>
                                            </div>
                                            {col.tip ? <p className={styles.hint}>{col.tip}</p> : null}
                                        </div>
                                    ))}
                                </div>
                            );
                        })}
                    </div>
                </section>

                <section className={styles.section}>
                    <h2 className={styles.sectionTitle}>Рабочие ситуации — внутренний SJT, пилотная версия</h2>
                    <div className={styles.card}>
                        {model.paei.map((row) => (
                            <div key={row.code}>
                                <div className={styles.roleRow}>
                                    <span
                                        className={`${styles.code} ${
                                            model.managementFocus?.code === row.code ? styles.roleLead : ""
                                        }`}
                                    >
                                        {row.name.slice(0, 1).toUpperCase()}
                                    </span>
                                    <div>
                                        <div className={styles.factorName}>
                                            {row.name}
                                        </div>
                                        <div className={`${styles.track} ${styles.plainTrack}`} style={{ marginTop: 6 }}>
                                            <span
                                                className={styles.fill}
                                                style={{
                                                    left: 0,
                                                    width: `${row.widthPct || 0}%`,
                                                    background: "#d7773f",
                                                }}
                                            />
                                        </div>
                                    </div>
                                    <span className={styles.val}>{row.count == null ? "—" : row.count}</span>
                                </div>
                                {row.tip ? <p className={styles.hint}>{row.tip}</p> : null}
                            </div>
                        ))}
                        <div className={styles.axis}>
                            <span>0</span>
                            <span>ориентир 6</span>
                            <span>24</span>
                        </div>
                        <p className={styles.qualityNum}>
                            Соответствие экспертному ключу: {model.qualityIndex == null ? "—" : model.qualityIndex} из 100
                        </p>
                        <div className={`${styles.track} ${styles.plainTrack}`}>
                            <span
                                className={styles.fill}
                                style={{ left: 0, width: `${donutPct}%`, background: "#55a44e" }}
                            />
                        </div>
                        <div className={styles.qualityCopy}>
                            <h3>{model.sjtCopy.title}</h3>
                            <p>{model.sjtCopy.text}</p>
                        </div>
                    </div>
                </section>

                <p className={styles.footer}>
                    Поведенческий блок и SJT являются внутренними пилотными инструментами. Результаты описывают
                    ответы кандидата, формируют гипотезы для интервью и не являются диагнозом, выводом о пригодности
                    или самостоятельным основанием для решения о найме. Значения округляются до целого; исходные
                    данные сохраняются без округления. Шкалы: пять факторов −100…+100, поведенческий пилот −8…+8,
                    фокус решений 0–24.
                </p>
            </div>
        </article>
    );
}
