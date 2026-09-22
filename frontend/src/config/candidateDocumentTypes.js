export const CANDIDATE_DOCUMENT_TYPES = [
    { value: "passport", label: "Паспорт", hint: "Приложите читаемые фотографии всех заполненных страниц." },
    { value: "snils", label: "СНИЛС" },
    { value: "inn", label: "ИНН", hint: "Можно приложить документ в электронном виде." },
    { value: "marriage_certificate", label: "Свидетельство о браке", hint: "Если состоите в браке." },
    { value: "children_birth_certificate", label: "Свидетельство о рождении ребёнка", hint: "При наличии детей. Для каждого ребёнка можно добавить отдельный файл." },
    { value: "education", label: "Диплом или другой документ об образовании" },
    { value: "employment_book", label: "Трудовая книжка или выписка из электронной трудовой", hint: "Электронную выписку можно скачать на Госуслугах." },
    { value: "military", label: "Военный билет или приписное удостоверение", hint: "При наличии воинской обязанности." },
    { value: "tachograph_card", label: "Активная карта тахографа", hint: "Только для водителей." },
    { value: "driver_license", label: "Водительское удостоверение", hint: "Только для водителей." },
    { value: "criminal_record_certificate", label: "Справка об отсутствии судимости", hint: "Можно заказать на Госуслугах и приложить в электронном виде." },
    { value: "medical_book", label: "Санитарная книжка", hint: "Только для водителей." },
    { value: "other", label: "Другой документ" },
];

export const CANDIDATE_DOCUMENT_LABELS = Object.fromEntries(
    CANDIDATE_DOCUMENT_TYPES.map(({ value, label }) => [value, label]),
);
