import { useState, useEffect } from "react";
import {
    assignVacancyToCandidate,
    changeCandidateVacancy,
    sendCandidateNotification,
    updateCandidateStatus,
    getCandidateStatus,
    sendOffer,
    getCandidateById,
    getTestResults,
    getCandidateActiveVacancy
} from "../../services/candidateApi";
import {getVacancies} from "../../services/vacancyApi";
import { useAlertContext } from "../../context/AlertContext";
import CandidateStatusControls from "./CandidateStatusControls";
import TestResultAccordionItem from "../tests/TestResultAccordionItem"
import {blockCandidate} from "../../services/blacklistApi";
import OfferModal from "./OfferModal";
import CandidateTimeline from "./CandidateTimeline";
import { relationVacancyName } from "../../utils/candidateMapper";
import { statusLabel as funnelStatusLabel } from "../../utils/candidateStatuses";
import { buildOfferLetterText } from "../../utils/interviewInvite";
import CandidateProfileCard, { Chip, Section, stageChipClass } from "./CandidateProfileCard";

export default function CandidateDetails({ candidate, onChange, isArchiveView = false }) {
    const [vacancies, setVacancies] = useState([]);
    const [showVacancySelect, setShowVacancySelect] = useState(false);
    const [headerStatus, setHeaderStatus] = useState(candidate?.status_code ?? candidate?.status ?? "");
    const [testResults, setTestResults] = useState([]);
    const [loadingTests, setLoadingTests] = useState(true);
    const { showAlert } = useAlertContext();
    const [offerModal, setOfferModal] = useState(false);
    const [selectedVacancyId, setSelectedVacancyId] = useState("");
    const [activeVacancy, setActiveVacancy] = useState(null);

    const defaultOfferText = buildOfferLetterText(candidate.full_name);

    const submitOffer = async (offerText, includeDocumentsLink = false) => {
        await sendOffer(candidate.id, offerText, includeDocumentsLink);
        showAlert("Оффер отправлен кандидату", "success");
        setOfferModal(false);
        onChange?.();
    };

    useEffect(() => {
        const fetchVacancies = async () => {
            try {
                const data = await getVacancies();
                setVacancies(Array.isArray(data) ? data : []);
            } catch (e) {
                console.error("Ошибка загрузки вакансий", e);
            }
        };
        fetchVacancies();
    }, []);

    useEffect(() => {
        if (!candidate?.id) return;
        Promise.resolve(getCandidateActiveVacancy(candidate.id))
            .then((data) => setActiveVacancy(data))
            .catch(() => setActiveVacancy(null));
    }, [candidate?.id]);

    useEffect(() => {
        const loadStatus = async () => {
            try {
                if (!candidate?.id) return;
                const statusData = await getCandidateStatus(candidate.id);
                const value = (typeof statusData === "object")
                    ? (statusData?.status ?? statusData?.code ?? statusData?.name ?? null)
                    : statusData;
                if (value != null) setHeaderStatus(value);
            } catch (e) {
                /* keep candidate.status */
            }
        };
        loadStatus();
    }, [candidate?.id]);

    useEffect(() => {
        if (candidate?.status != null) setHeaderStatus(candidate.status);
    }, [candidate?.status]);

    useEffect(() => {
        if (!candidate?.id) return;
        setLoadingTests(true);
        Promise.resolve(getTestResults(candidate.id))
            .then((data) => {
                if (Array.isArray(data)) setTestResults(data);
                else if (data?.items && Array.isArray(data.items)) setTestResults(data.items);
                else setTestResults([]);
            })
            .catch(() => setTestResults([]))
            .finally(() => setLoadingTests(false));
    }, [candidate?.id]);

    const handleBlock = async () => {
        if (!window.confirm(`Заблокировать кандидата ${candidate.full_name}? Он попадёт в чёрный список.`)) return;
        try {
            await blockCandidate(candidate.id);
            showAlert("Кандидат добавлен в чёрный список", "success");
            onChange?.();
        } catch (e) {
            showAlert(`Ошибка ${e.message}`, "error");
        }
    };

    const handleAssignVacancy = async (vacancyId) => {
        if (!vacancyId) {
            showAlert("Сначала выберите вакансию", "warning");
            return;
        }
        const vacancy = vacancies.find((v) => v.id === parseInt(vacancyId, 10));
        if (!vacancy) return;
        if (!window.confirm(`Назначить вакансию «${vacancy.name}» кандидату ${candidate.full_name}?`)) {
            setShowVacancySelect(false);
            return;
        }
        try {
            if (activeVacancy) {
                await changeCandidateVacancy(candidate.id, Number(vacancyId));
            } else {
                await assignVacancyToCandidate(candidate.id, Number(vacancyId));
            }
            try {
                await sendCandidateNotification(candidate.id, Number(vacancyId));
            } catch (e) {
                const msg = String(e?.message || e || "");
                if (msg.includes("BotUser not found")) {
                    showAlert("Вакансия назначена. У кандидата нет BotUser — уведомление не отправлено.", "warning");
                } else {
                    throw e;
                }
            }
            if (!activeVacancy) {
                await updateCandidateStatus(candidate.id, "откликнулся");
            }
            const fresh = await getCandidateById(candidate.id);
            candidate.status = fresh?.status ?? candidate.status;
            candidate.vacancy_id = fresh?.vacancy_id ?? Number(vacancyId);
            setShowVacancySelect(false);
            showAlert(
                activeVacancy
                    ? "Вакансия изменена. Кандидат возвращён на этап «Отклик получен»."
                    : "Вакансия назначена. Кандидат возвращён в активный подбор.",
                "success"
            );
            onChange?.();
        } catch (e) {
            showAlert(`Ошибка ${e.message}`, "error");
        }
    };

    const resumeUrl = candidate.hh_resume_link || candidate.resume;
    const statusLabel = funnelStatusLabel(headerStatus || candidate?.status) || headerStatus || candidate?.status || "Не указан";
    const vacancyTitle =
        relationVacancyName(activeVacancy)
        || candidate.vacancy_name
        || candidate.last_vacancy_title
        || null;
    const canChangeVacancy = candidate.stage !== "нанят" && candidate.stage !== "в черном списке";

    return (
        <div className="space-y-5">
            <CandidateProfileCard
                candidate={candidate}
                vacancyTitle={vacancyTitle}
                showAi
                badges={(
                    <>
                        {candidate.stage ? (
                            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ring-1 ${stageChipClass(candidate.stage)}`}>
                                {candidate.stage}
                            </span>
                        ) : null}
                        <Chip>{statusLabel}</Chip>
                    </>
                )}
                actions={(
                    <>
                        <button
                            type="button"
                            onClick={() => setOfferModal(true)}
                            disabled={candidate.offer_sent === true}
                            className="px-3.5 py-2 rounded-xl bg-[#e0bb48] text-slate-900 text-sm font-semibold hover:bg-[#d4af3a] disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                        >
                            {candidate.offer_sent ? "Оффер отправлен" : "Направить оффер"}
                        </button>
                        {resumeUrl ? (
                            <a
                                href={resumeUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50"
                            >
                                Открыть резюме
                            </a>
                        ) : null}
                        {canChangeVacancy ? (
                            <button
                                type="button"
                                onClick={() => setShowVacancySelect((v) => !v)}
                                className="px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50"
                            >
                                {vacancyTitle ? "Сменить вакансию" : "Привязать к вакансии"}
                            </button>
                        ) : null}
                        <button
                            type="button"
                            onClick={handleBlock}
                            className="px-3.5 py-2 rounded-xl border border-rose-200 bg-white text-rose-700 text-sm font-medium hover:bg-rose-50"
                        >
                            В чёрный список
                        </button>
                    </>
                )}
                belowHeader={
                    showVacancySelect && canChangeVacancy ? (
                        <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-2">
                            <p className="text-sm text-slate-600">
                                Новая вакансия станет активной, а кандидат вернётся на этап «Отклик получен». История предыдущей вакансии сохранится.
                            </p>
                            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Вакансия
                            </label>
                            <select
                                value={selectedVacancyId}
                                onChange={(e) => setSelectedVacancyId(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/40"
                            >
                                <option value="">Выберите вакансию</option>
                                {vacancies.map((vacancy) => (
                                    <option key={vacancy.id} value={vacancy.id}>{vacancy.name}</option>
                                ))}
                            </select>
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    onClick={() => handleAssignVacancy(selectedVacancyId)}
                                    disabled={!selectedVacancyId}
                                    className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
                                >
                                    Назначить
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setShowVacancySelect(false)}
                                    className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50"
                                >
                                    Отмена
                                </button>
                            </div>
                        </div>
                    ) : null
                }
            />

            <Section title="Воронка и статус">
                <CandidateStatusControls candidate={candidate} onChange={onChange} showOffer={false} />
            </Section>

            <Section title="Результаты тестов">
                {loadingTests ? (
                    <p className="text-slate-400 text-sm">Загрузка…</p>
                ) : testResults.length === 0 ? (
                    <p className="text-slate-400 text-sm">Нет результатов тестов</p>
                ) : (
                    <div className="space-y-3">
                        {testResults.map((result) => (
                            <TestResultAccordionItem key={result.id} result={result} />
                        ))}
                    </div>
                )}
            </Section>

            <CandidateTimeline
                candidateId={candidate.id}
                vacancyId={activeVacancy?.id || activeVacancy?.vacancy_id}
                refreshKey={`${candidate.status || ""}-${candidate.stage || ""}-${headerStatus || ""}`}
                onChanged={onChange}
            />
            <OfferModal
                open={offerModal}
                defaultText={defaultOfferText}
                onClose={() => setOfferModal(false)}
                onSubmit={submitOffer}
            />
        </div>
    );
}
