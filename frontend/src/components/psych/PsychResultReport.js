import { useRef, useState } from "react";
import styles from "./psychResultReport.module.css";
import PsychResultPdfDocument from "./PsychResultPdfDocument";
import { printPsychResultPdf } from "../../psychometrics/psychPdfExport";
import {
    DISC_CONTEXTS,
    discCaption,
    formatSigned,
    toPsychReportModel,
} from "../../psychometrics/psychReportViewModel";

function Tip({ label, tip, children }) {
    if (!tip) return children || label;
    return (
        <span className={styles.tip} tabIndex={0}>
            {children || label}
            <span className={styles.info}>i</span>
            <span className={styles.tooltip}>{tip}</span>
        </span>
    );
}

function avpBarStyle(signed) {
    if (signed == null || signed === 0) {
        return { left: "50%", width: "2px" };
    }
    const pct = Math.min(50, (Math.abs(signed) / 100) * 50);
    if (signed > 0) {
        return {
            left: "50%",
            width: `${pct}%`,
            background: signed >= 68 ? "#11b8d7" : "#3b66f0",
        };
    }
    return {
        left: `${50 - pct}%`,
        width: `${pct}%`,
        background: "#3b66f0",
    };
}

function DiscCard({ title, rows }) {
    return (
        <div className={`${styles.card} ${styles.disc}`}>
            <h3>{title}</h3>
            <div className={styles.caption}>{discCaption(rows)}</div>
            <div className={styles.discBars}>
                {rows.map((col) => (
                    <div
                        key={col.code}
                        className={`${styles.dcol} ${col.positive ? styles.pos : styles.neg}`}
                        style={{ "--h": `${col.px || 0}px`, "--c": col.color }}
                    >
                        <span className={styles.v}>{formatSigned(col.raw)}</span>
                        <i className={styles.b} />
                        <span className={styles.lab}>
                            <Tip label={col.name} tip={col.tip}>
                                {col.name.slice(0, 1).toUpperCase()}
                            </Tip>
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function PsychResultReport({ result, onClose }) {
    const model = toPsychReportModel(result);
    const toneClass = styles[model.qualityTone] || "";
    const donutPct = model.qualityIndex == null ? 0 : Math.max(0, Math.min(100, model.qualityIndex));
    const [savingPdf, setSavingPdf] = useState(false);
    const pdfRef = useRef(null);

    const handleSavePdf = async () => {
        try {
            setSavingPdf(true);
            await printPsychResultPdf({
                root: pdfRef.current,
                fullName: model.fullName,
                position: model.position,
                takenAt: result?.taken_at || model.takenAt,
                id: result?.id,
            });
        } catch (err) {
            window.alert(`Не удалось сохранить PDF: ${err?.message || err}`);
        } finally {
            setSavingPdf(false);
        }
    };

    return (
        <>
        <section className={`${styles.screen} psych-result-print-root`} data-testid="psych-result-detail">
            <header className={styles.top}>
                <div>
                    <div className={styles.eyebrow}>ОТЧЁТ ПО РЕЗУЛЬТАТАМ ОЦЕНКИ КАНДИДАТА</div>
                    <h1 className={styles.title}>{model.fullName}</h1>
                    <div className={styles.sub}>
                        {model.position}
                        {model.position ? " · " : ""}
                        {model.takenAt}
                        {model.birthDate && model.birthDate !== "—" ? ` · др ${model.birthDate}` : ""}
                    </div>
                </div>
                <div className={`${styles.actions} psych-result-print-hide`}>
                    <button
                        type="button"
                        className={styles.pdf}
                        data-testid="psych-save-pdf"
                        disabled={savingPdf}
                        onClick={handleSavePdf}
                    >
                        {savingPdf ? "Сохранение…" : "Сохранить PDF"}
                    </button>
                    <button type="button" className={styles.close} onClick={onClose}>
                        Закрыть
                    </button>
                </div>
            </header>

            <div className={styles.summary}>
                <div className={styles.metric}>
                    <small>КАЧЕСТВО</small>
                    <b className={toneClass}>● {model.qualityStatus}</b>
                </div>
                <div className={styles.metric}>
                    <small>АКТИВНОЕ ВРЕМЯ</small>
                    <b>{model.activeTime}</b>
                </div>
                <div className={styles.metric}>
                    <small>ЧС</small>
                    <b data-testid="psych-chs">{model.chs}</b>
                </div>
                <div className={styles.metric}>
                    <small>ЧМ</small>
                    <b data-testid="psych-chm">{model.chm}</b>
                </div>
                <div className={styles.metric}>
                    <small>ПОВЕДЕНЧЕСКАЯ ТЕНДЕНЦИЯ · ПИЛОТ</small>
                    <b>
                        {model.behaviorPreference ? (
                            <Tip tip={model.behaviorPreference.tip}>
                                {model.behaviorPreference.label}
                            </Tip>
                        ) : (
                            "—"
                        )}
                    </b>
                </div>
                <div className={styles.metric}>
                    <small>ФОКУС РЕШЕНИЙ · ПИЛОТНЫЙ SJT</small>
                    <b>
                        {model.managementFocus ? (
                            <Tip tip={model.managementFocus.tip}>
                                {model.managementFocus.label}
                            </Tip>
                        ) : (
                            "—"
                        )}
                    </b>
                </div>
            </div>

            <main className={styles.content}>
                <div className={styles.grid2}>
                    <div className={`${styles.card} ${styles.pad}`}>
                        <div className={styles.cardHead}>
                            <h2>Пять факторов BFAS</h2>
                            <span className={styles.pill}>Шкала −100…+100</span>
                        </div>
                        {model.factors.map((row) => (
                            <div className={styles.avpRow} key={row.code}>
                                <div className={styles.name}>
                                    <Tip label={row.name} tip={row.tip} />
                                </div>
                                <div className={styles.scale}>
                                    <i className={styles.valueLine} style={avpBarStyle(row.signed)} />
                                </div>
                                <div className={styles.score}>{formatSigned(row.signed)}</div>
                                <div className={styles.level}>{row.level}</div>
                            </div>
                        ))}
                        <div className={styles.axis}>
                            <span>−100</span>
                            <span>−68</span>
                            <span>−32</span>
                            <span>0</span>
                            <span>+32</span>
                            <span>+68</span>
                            <span>+100</span>
                        </div>
                        <div className={styles.note}>
                            Границы отображения: −68, −32, +32 и +68. Это интерфейсный индекс, а не процентиль.
                        </div>
                    </div>
                    <aside className={styles.callout}>
                        <h2>Наблюдения для интервью</h2>
                        <p>{model.insight.text}</p>
                        <div className={styles.tags}>
                            {model.insight.tags.map((tag) => (
                                <span className={styles.tag} key={tag}>
                                    {tag}
                                </span>
                            ))}
                        </div>
                    </aside>
                </div>

                <div className={styles.sectionTitle}>Рабочие предпочтения — внутренний пилотный поведенческий блок</div>
                <div className={styles.grid3}>
                    {DISC_CONTEXTS.map((ctx) => (
                        <DiscCard key={ctx.key} title={ctx.title} rows={model.disc[ctx.key] || []} />
                    ))}
                </div>

                <div className={styles.sectionTitle}>Рабочие ситуации — внутренний SJT, пилотная версия</div>
                <div className={styles.management}>
                    <div className={`${styles.card} ${styles.pad}`}>
                        <div className={styles.cardHead}>
                            <h2>Фокус выбранных решений</h2>
                            <span className={styles.pill}>Шкала 0–24</span>
                        </div>
                        {model.paei.map((row) => (
                            <div className={styles.roleRow} key={row.code}>
                                <span
                                    className={`${styles.roleCode} ${
                                        model.managementFocus?.code === row.code ? styles.roleLead : ""
                                    }`}
                                >
                                    {row.name.slice(0, 1).toUpperCase()}
                                </span>
                                <span>
                                    <Tip label={row.name} tip={row.tip} />
                                </span>
                                <div className={styles.roleScale}>
                                    <div className={styles.roleFill} style={{ width: `${row.widthPct}%` }} />
                                </div>
                                <b>{row.count == null ? "—" : row.count}</b>
                            </div>
                        ))}
                        <div className={styles.roleAxis}>
                            <span>0</span>
                            <span>ориентир 6</span>
                            <span>24</span>
                        </div>
                    </div>
                    <div className={`${styles.card} ${styles.pad} ${styles.donutWrap}`}>
                        <div
                            className={styles.donut}
                            style={{
                                background: `conic-gradient(#55a44e 0 ${donutPct}%, #edf0f4 ${donutPct}% 100%)`,
                            }}
                        >
                            <b>{model.qualityIndex == null ? "—" : model.qualityIndex}</b>
                            <span>из 100</span>
                        </div>
                        <div className={styles.donutCopy}>
                            <h3>{model.sjtCopy.title}</h3>
                            <p>{model.sjtCopy.text}</p>
                        </div>
                    </div>
                </div>
            </main>
            <div className={styles.footer}>
                Поведенческий блок и SJT являются внутренними пилотными инструментами. Результаты описывают ответы
                кандидата, формируют гипотезы для интервью и не являются диагнозом, выводом о пригодности или
                самостоятельным основанием для решения о найме. Все значения в интерфейсе округляются до целого;
                исходные данные сохраняются без округления.
            </div>
        </section>
        <div className="pdf-source-host" aria-hidden="true">
            <div ref={pdfRef}>
                <PsychResultPdfDocument model={model} />
            </div>
        </div>
        </>
    );
}
