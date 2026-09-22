import { experienceLabel, genderLabel } from "../../utils/hhLabels";
import { formatTelegramUsername, telegramHref, formatEmail } from "../../utils/candidateMapper";
import { parseWorkExperienceList } from "../../utils/candidateActivity";
import { getCandidateNumerology } from "../../utils/candidateNumerology";
import { formatDateRu } from "../../utils/dateFormat";

function asList(value) {
    if (value == null || value === "") return [];
    return Array.isArray(value) ? value.filter(Boolean) : [value];
}

export function initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return "?";
    return parts.slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

export function stageChipClass(stage) {
    if (stage === "нанят") return "bg-emerald-50 text-emerald-800 ring-emerald-200";
    if (stage === "в процессе найма") return "bg-sky-50 text-sky-800 ring-sky-200";
    if (stage === "архивирован") return "bg-slate-100 text-slate-700 ring-slate-200";
    if (stage === "в черном списке") return "bg-rose-50 text-rose-800 ring-rose-200";
    return "bg-slate-100 text-slate-700 ring-slate-200";
}

export function Section({ title, children, className = "" }) {
    return (
        <section className={`rounded-2xl border border-slate-200/80 bg-white p-5 ${className}`}>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                {title}
            </h3>
            {children}
        </section>
    );
}

export function InfoItem({ label, value, href }) {
    if (value == null || value === "" || value === false) return null;
    return (
        <div className="min-w-0">
            <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</dt>
            <dd className="mt-0.5 text-sm text-slate-800 break-words">
                {href ? (
                    <a href={href} target="_blank" rel="noreferrer" className="text-sky-700 hover:underline">
                        {value}
                    </a>
                ) : (
                    value
                )}
            </dd>
        </div>
    );
}

export function Chip({ children, tone = "slate" }) {
    const tones = {
        slate: "bg-slate-100 text-slate-700",
        sky: "bg-sky-50 text-sky-800",
        violet: "bg-violet-50 text-violet-800",
        emerald: "bg-emerald-50 text-emerald-800",
        amber: "bg-[#cda834]/15 text-slate-800",
    };
    return (
        <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium ${tones[tone] || tones.slate}`}>
            {children}
        </span>
    );
}

function experienceJobsFromCandidate(candidate) {
    if (Array.isArray(candidate?.experience) && candidate.experience.length) {
        return candidate.experience.filter(Boolean);
    }
    return parseWorkExperienceList(candidate?.other_work_expirience);
}

/**
 * Visual candidate card (header + about + optional AI + resume sections).
 * Hiring funnel / tests / timeline stay in CandidateDetails.
 */
export default function CandidateProfileCard({
    candidate,
    vacancyTitle,
    showAi = true,
    badges,
    actions,
    belowHeader,
    aiHint,
}) {
    const hardSkills = asList(candidate.hard_skills);
    const programs = asList(candidate.work_programs);
    const languages = asList(candidate.languages);
    const hobbies = asList(candidate.hobbies);
    const otherExp = experienceJobsFromCandidate(candidate);
    const education = asList(candidate.education);
    const aiScore = candidate.ai_score;
    const hasAiScore = aiScore !== null && aiScore !== undefined;
    const birth = candidate.birth_date || candidate.birthdate;
    const numerology = getCandidateNumerology(birth);
    const telegram = formatTelegramUsername(candidate.telegram_username);
    const email = formatEmail(candidate.email);

    return (
        <div className="space-y-5">
            <header className="rounded-2xl border border-slate-200/80 bg-gradient-to-br from-slate-50 to-white p-5">
                <div className="flex flex-col sm:flex-row sm:items-start gap-5">
                    {candidate.photo_url ? (
                        <img
                            src={candidate.photo_url}
                            alt={candidate.full_name}
                            className="w-24 h-24 sm:w-28 sm:h-28 object-cover rounded-2xl ring-1 ring-slate-200/80 shadow-sm shrink-0"
                        />
                    ) : (
                        <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl bg-[#cda834]/20 text-slate-800 flex items-center justify-center text-2xl font-bold shrink-0 ring-1 ring-[#cda834]/30">
                            {initials(candidate.full_name)}
                        </div>
                    )}
                    <div className="min-w-0 flex-1 space-y-3">
                        <div>
                            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                                {candidate.full_name || "Кандидат"}
                            </h2>
                            <p className="mt-1 text-sm text-slate-600">
                                {vacancyTitle
                                    ? <>Вакансия: <span className="font-medium text-slate-800">{vacancyTitle}</span></>
                                    : <span className="text-slate-400">Вакансия не привязана</span>}
                            </p>
                            {(candidate.phone_number || telegram || email) ? (
                                <p className="mt-1.5 text-sm text-slate-600 flex flex-wrap gap-x-3 gap-y-1">
                                    {candidate.phone_number ? (
                                        <a href={`tel:${candidate.phone_number}`} className="hover:text-slate-900">
                                            {candidate.phone_number}
                                        </a>
                                    ) : null}
                                    {telegram ? (
                                        <a
                                            href={telegramHref(telegram)}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="text-sky-700 hover:underline"
                                        >
                                            {telegram}
                                        </a>
                                    ) : null}
                                    {email ? (
                                        <a href={`mailto:${email}`} className="text-sky-700 hover:underline">
                                            {email}
                                        </a>
                                    ) : null}
                                </p>
                            ) : null}
                            <div className="mt-2 flex flex-wrap gap-1.5">
                                {badges}
                            </div>
                        </div>
                        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
                        {belowHeader}
                    </div>
                </div>
            </header>

            {!showAi && aiHint ? (
                <p className="text-sm text-slate-500 bg-slate-50 border border-slate-100 rounded-2xl px-4 py-3">
                    {aiHint}
                </p>
            ) : null}

            <div className={`grid grid-cols-1 gap-4 ${showAi ? "lg:grid-cols-5" : ""}`}>
                <Section title="О кандидате" className={showAi ? "lg:col-span-3" : ""}>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                        <InfoItem label="Пол" value={genderLabel(candidate.gender) || candidate.gender} />
                        <InfoItem label="Дата рождения" value={formatDateRu(birth, null)} />
                        <InfoItem label="ЧС" value={numerology.cs} />
                        <InfoItem label="ЧМ" value={numerology.cm} />
                        <InfoItem label="Возраст" value={candidate.age ? `${candidate.age} лет` : null} />
                        <InfoItem label="Город" value={candidate.area || candidate.city} />
                        <InfoItem label="Телефон" value={candidate.phone_number} href={candidate.phone_number ? `tel:${candidate.phone_number}` : null} />
                        <InfoItem
                            label="Telegram"
                            value={telegram}
                            href={telegramHref(telegram)}
                        />
                        <InfoItem
                            label="Почта"
                            value={email}
                            href={email ? `mailto:${email}` : null}
                        />
                        <InfoItem label="Семья" value={candidate.marital_status} />
                        <InfoItem
                            label="Ожидания по зарплате"
                            value={
                                candidate.salary_expectations
                                    ? `${Number(candidate.salary_expectations).toLocaleString("ru-RU")} ₽`
                                    : candidate.salary_label || null
                            }
                        />
                        <InfoItem
                            label="Активный поиск"
                            value={
                                candidate.active_search === true
                                    ? "Да"
                                    : candidate.active_search === false
                                      ? "Нет"
                                      : candidate.job_search_status || null
                            }
                        />
                        <InfoItem
                            label="Резюме обновлено"
                            value={candidate.resume_updated_label || formatDateRu(candidate.resume_update_date, null)}
                        />
                    </dl>
                </Section>

                {showAi ? (
                    <Section title="Оценка AI" className="lg:col-span-2">
                        <div className="flex items-end gap-2">
                            <span className="text-3xl font-bold text-slate-900 tabular-nums" data-testid="candidate-ai-score">
                                {hasAiScore ? Number(aiScore).toFixed(0) : "—"}
                            </span>
                            <span className="text-sm text-slate-400 mb-1">/ 100</span>
                        </div>
                        <div className="mt-3 h-2 rounded-full bg-slate-100 overflow-hidden">
                            <div
                                className="h-full rounded-full bg-[#cda834] transition-all"
                                style={{ width: `${hasAiScore ? Math.min(100, Math.max(0, Number(aiScore))) : 0}%` }}
                            />
                        </div>
                        <p className="mt-3 text-sm text-slate-600 leading-relaxed" data-testid="candidate-ai-comment">
                            {candidate.ai_comment || "Комментария AI пока нет."}
                        </p>
                    </Section>
                ) : null}
            </div>

            {candidate.feedback ? (
                <Section title="Отзыв кандидата">
                    <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{candidate.feedback}</p>
                </Section>
            ) : null}

            {candidate.about ? (
                <Section title="О себе">
                    <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{candidate.about}</p>
                </Section>
            ) : null}

            <Section title="Опыт работы">
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3">
                    <InfoItem
                        label="Общий опыт"
                        value={
                            experienceLabel(candidate.total_work_expirience)
                            || candidate.total_work_expirience
                            || candidate.experience_label
                        }
                    />
                    <InfoItem label="На релевантной позиции" value={candidate.relevant_position_expirience} />
                    <InfoItem label="На конкретной позиции" value={candidate.certain_position_expirience} />
                    <InfoItem
                        label="Средний стаж"
                        value={candidate.average_service_length ? `${candidate.average_service_length} лет` : null}
                    />
                </dl>
                {otherExp.length > 0 ? (
                    <ul className="mt-4 space-y-3">
                        {otherExp.map((job, i) => (
                            <li key={i} className="rounded-xl border border-slate-100 bg-slate-50/80 p-4">
                                <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1">
                                    <p className="text-sm font-semibold text-slate-900">{job.title || "Опыт работы"}</p>
                                    {job.period ? <p className="text-xs text-slate-500">{job.period}</p> : null}
                                </div>
                                {job.company ? <p className="mt-0.5 text-sm text-slate-700">{job.company}</p> : null}
                                {(job.industry || job.region) ? (
                                    <p className="mt-1 text-xs text-slate-500">
                                        {[job.industry, job.region].filter(Boolean).join(" · ")}
                                    </p>
                                ) : null}
                                {job.description ? (
                                    <p className="mt-2 text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
                                        {job.description}
                                    </p>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                ) : null}
            </Section>

            {education.length > 0 ? (
                <Section title="Образование">
                    <ul className="space-y-2">
                        {education.map((item, i) => (
                            <li key={i} className="text-sm text-slate-800 pl-3 border-l-2 border-[#cda834]/60">
                                {item}
                            </li>
                        ))}
                    </ul>
                </Section>
            ) : null}

            {(hardSkills.length > 0 || programs.length > 0) ? (
                <Section title="Навыки">
                    {hardSkills.length > 0 ? (
                        <div className="mb-3">
                            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-1.5">Профессиональные</p>
                            <div className="flex flex-wrap gap-1.5">
                                {hardSkills.map((skill, i) => (
                                    <Chip key={i} tone="sky">{skill}</Chip>
                                ))}
                            </div>
                        </div>
                    ) : null}
                    {programs.length > 0 ? (
                        <div>
                            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-1.5">Программы</p>
                            <div className="flex flex-wrap gap-1.5">
                                {programs.map((prog, i) => (
                                    <Chip key={i} tone="violet">{prog}</Chip>
                                ))}
                            </div>
                        </div>
                    ) : null}
                </Section>
            ) : null}

            {languages.length > 0 ? (
                <Section title="Языки">
                    <div className="flex flex-wrap gap-1.5">
                        {languages.map((lang, i) => (
                            <Chip key={i} tone="emerald">{lang}</Chip>
                        ))}
                    </div>
                </Section>
            ) : null}

            {(hobbies.length > 0 || candidate.personal_characteristics) ? (
                <Section title="Личные качества">
                    {candidate.personal_characteristics ? (
                        <p className="text-sm text-slate-700 leading-relaxed mb-2">{candidate.personal_characteristics}</p>
                    ) : null}
                    {hobbies.length > 0 ? (
                        <p className="text-sm text-slate-600">
                            <span className="text-slate-400 text-xs font-medium uppercase tracking-wide">Хобби · </span>
                            {hobbies.join(", ")}
                        </p>
                    ) : null}
                </Section>
            ) : null}
        </div>
    );
}
