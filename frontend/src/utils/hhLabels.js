/** Human-readable Russian labels for HH.ru dictionary ids. */

export const HH_SCHEDULE_LABELS = {
    fullDay: "Полный день",
    shift: "Сменный график",
    flexible: "Гибкий график",
    remote: "Удалённая работа",
    flyInFlyOut: "Вахтовый метод",
};

export const HH_EMPLOYMENT_LABELS = {
    full: "Полная занятость",
    part: "Частичная занятость",
    project: "Проектная работа",
    volunteer: "Волонтёрство",
    probation: "Стажировка",
};

export const HH_EXPERIENCE_LABELS = {
    noExperience: "Нет опыта",
    between1And3: "От 1 года до 3 лет",
    between3And6: "От 3 до 6 лет",
    moreThan6: "Более 6 лет",
};

export const HH_VACANCY_TYPE_LABELS = {
    open: "Открытая",
    closed: "Закрытая",
    anonymous: "Анонимная",
    direct: "Рекламная",
};

export const GENDER_LABELS = {
    male: "мужчина",
    female: "женщина",
    мужчина: "мужчина",
    женщина: "женщина",
};

/**
 * Resolve a display label for a HH dictionary id.
 * Prefers live dictionary items ({id, name}), then static fallbacks, then the raw id.
 */
export function labelFromDict(items, id, fallbackMap = {}) {
    if (id == null || id === "") return "";
    const key = String(id);
    const list = Array.isArray(items) ? items : [];
    const found = list.find((item) => String(item?.id) === key);
    if (found?.name) return String(found.name);
    if (found?.title) return String(found.title);
    if (fallbackMap[key]) return fallbackMap[key];
    return key;
}

export function scheduleLabel(id, dictionaries) {
    return labelFromDict(dictionaries?.schedules, id, HH_SCHEDULE_LABELS);
}

export function employmentLabel(id, dictionaries) {
    return labelFromDict(dictionaries?.employment, id, HH_EMPLOYMENT_LABELS);
}

export function experienceLabel(id, dictionaries) {
    return labelFromDict(dictionaries?.experience, id, HH_EXPERIENCE_LABELS);
}

export function vacancyTypeLabel(id, dictionaries) {
    return labelFromDict(dictionaries?.vacancyTypes || dictionaries?.vacancy_type, id, HH_VACANCY_TYPE_LABELS);
}

export function genderLabel(value) {
    if (value == null || value === "") return "";
    return GENDER_LABELS[value] || GENDER_LABELS[String(value).toLowerCase()] || String(value);
}
