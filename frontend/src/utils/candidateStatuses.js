/**
 * Candidate status funnel (matches backend CandidateStatus enum).
 * Tree is for UI hierarchy only — values are flat strings in API/DB.
 */

export const CANDIDATE_STATUS_TREE = [
    { value: "холодный контакт" },
    { value: "не подходит" },
    { value: "отказался" },
    {
        value: "откликнулся",
        children: [
            {
                value: "тест: отправлен",
                children: [
                    { value: "тест: не прошли" },
                    {
                        value: "тест: пройден",
                        children: [
                            { value: "подумать" },
                            {
                                value: "собес",
                                children: [
                                    { value: "отказ" },
                                    { value: "оффер принят" },
                                    { value: "Full documents" },
                                    {
                                        value: "ВНР",
                                        children: [{ value: "уволился" }],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    },
];

export const ARCHIVE_STATUS_VALUES = new Set([
    "не подходит",
    "отказался",
    "отказ",
    "уволился",
]);

export const HIRE_STATUS_VALUE = "ВНР";

export const STATUS_LABELS = {
    "холодный контакт": "Холодный контакт",
    "не подходит": "Не подходит",
    "отказался": "Отказался",
    "откликнулся": "Откликнулся",
    "тест: отправлен": "Тест отправлен",
    "тест: не прошли": "Тест не пройден",
    "тест: пройден": "Тест пройден",
    собес: "Собеседование",
    подумать: "Подумать",
    "оффер принят": "Оффер принят",
    "Full documents": "Все документы",
    отказ: "Отказ",
    ВНР: "Вышел на работу",
    уволился: "Уволился",
};

export const STATUS_NEXT_ACTIONS = {
    "холодный контакт": "Связаться с кандидатом",
    "не подходит": "При необходимости вернуть в подбор",
    отказался: "При необходимости вернуть в подбор",
    откликнулся: "Провести первичный разбор",
    "тест: отправлен": "Дождаться результата теста",
    "тест: не прошли": "Вернуть в подбор или оставить в архиве",
    "тест: пройден": "Назначить собеседование",
    собес: "Провести собеседование и зафиксировать решение",
    подумать: "Вернуться к решению по кандидату",
    "оффер принят": "Запросить документы для трудоустройства",
    "Full documents": "Подтвердить выход на работу",
    отказ: "При необходимости вернуть в подбор",
    ВНР: "Сопровождать сотрудника",
    уволился: "Карточка завершена",
};

export const STATUS_STAGES = {
    "холодный контакт": "Поиск", "не подходит": "Первичный отбор", отказался: "Подбор завершён",
    откликнулся: "Первичный отбор", "тест: отправлен": "Тестирование", "тест: не прошли": "Тестирование",
    "тест: пройден": "Тестирование", собес: "Собеседование", подумать: "Принятие решения",
    "оффер принят": "Оформление", "Full documents": "Оформление", отказ: "Подбор завершён",
    ВНР: "Трудоустройство", уволился: "Трудоустройство",
};

export const STATUS_STATES = {
    "холодный контакт": "Контакт ещё не установлен", "не подходит": "Завершён: кандидат не подходит",
    отказался: "Архив: отказ кандидата", откликнулся: "Ожидает рассмотрения",
    "тест: отправлен": "Ожидается результат", "тест: не прошли": "Результат: не пройден",
    "тест: пройден": "Результат: пройден", собес: "В работе", подумать: "Решение отложено",
    "оффер принят": "Оффер принят кандидатом", "Full documents": "Документы собраны",
    отказ: "Архив: отказ работодателя", ВНР: "Сотрудник работает", уволился: "Архив: сотрудник уволился",
};

export const STATUS_TRANSITIONS = {
    "холодный контакт": ["откликнулся", "не подходит", "отказался"],
    откликнулся: ["тест: отправлен", "собес", "подумать", "не подходит", "отказался", "отказ"],
    "тест: отправлен": ["тест: не прошли", "тест: пройден", "отказался", "отказ"],
    "тест: не прошли": ["откликнулся"],
    "тест: пройден": ["подумать", "собес", "отказался", "отказ"],
    подумать: ["тест: отправлен", "собес", "оффер принят", "отказался", "отказ"],
    собес: ["подумать", "оффер принят", "ВНР", "отказался", "отказ"],
    "оффер принят": ["Full documents", "ВНР", "отказался", "отказ"],
    "Full documents": ["ВНР", "отказался", "отказ"],
    ВНР: ["уволился"],
    "не подходит": ["откликнулся"],
    отказался: ["откликнулся"],
    отказ: ["откликнулся"],
    уволился: [],
};

export const CARD_STATUS_ACTIONS = [
    { status: "собес", label: "На собеседование", tone: "sky" },
    { status: "подумать", label: "Подумать", tone: "amber" },
    { status: "отказ", label: "Отказать", tone: "rose" },
];

export function statusLabel(status) {
    const raw = String(status || "").trim();
    if (!raw) return "";
    return STATUS_LABELS[raw] || raw;
}

export function candidateState(stage, status) {
    const raw = String(status || "").trim();
    const rawStage = String(stage || "").trim();
    if (rawStage === "архивирован" && !String(STATUS_STATES[raw] || "").startsWith("Архив:")) return "Архив";
    if (rawStage === "нанят" && !STATUS_STATES[raw]) return "Сотрудник работает";
    if (rawStage === "в черном списке") return "Чёрный список";
    return STATUS_STATES[raw] || "Состояние не указано";
}

export function statusStage(status, catalog = []) {
    const raw = String(status || "").trim();
    const item = catalog.find((entry) => String(entry.code || entry.status) === raw);
    return item?.stage || STATUS_STAGES[raw] || "Этап не указан";
}

export function statusState(status, candidateStage, catalog = []) {
    const raw = String(status || "").trim();
    const item = catalog.find((entry) => String(entry.code || entry.status) === raw);
    if (candidateStage === "в черном списке") return "Чёрный список";
    return item?.state || candidateState(candidateStage, raw);
}

export function statusNextAction(status, catalog = []) {
    const raw = String(status || "").trim();
    const item = catalog.find((entry) => String(entry.code || entry.status) === raw);
    return item?.nextAction || item?.next_action || STATUS_NEXT_ACTIONS[raw] || "Уточнить следующий шаг";
}

export function allowedStatusTransitions(status, catalog = []) {
    const raw = String(status || "").trim();
    const item = catalog.find((entry) => String(entry.code || entry.status) === raw);
    if (item && Array.isArray(item.allowedTransitions)) return item.allowedTransitions;
    if (item && Array.isArray(item.allowed_transitions)) return item.allowed_transitions;
    return STATUS_TRANSITIONS[raw] || [];
}

export function flattenStatusTree(nodes = CANDIDATE_STATUS_TREE, depth = 0, acc = []) {
    for (const node of nodes) {
        acc.push({ value: node.value, depth, hasChildren: Boolean(node.children?.length) });
        if (node.children?.length) {
            flattenStatusTree(node.children, depth + 1, acc);
        }
    }
    return acc;
}

export function isArchiveStatus(status) {
    return ARCHIVE_STATUS_VALUES.has(String(status || "").trim());
}

export function isHireStatus(status) {
    return String(status || "").trim() === HIRE_STATUS_VALUE;
}
