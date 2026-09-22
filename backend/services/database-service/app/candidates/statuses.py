"""Canonical candidate funnel catalog and transition policy.

Database enum values are intentionally preserved during the stabilization phase.
In particular, ``Full documents`` remains a storage code while public copy is Russian.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.db.v1.enums import CandidateStatus


@dataclass(frozen=True)
class CandidateStatusDefinition:
    label: str
    stage: str
    state: str
    next_action: str


STATUS_DEFINITIONS: dict[CandidateStatus, CandidateStatusDefinition] = {
    CandidateStatus.cold_contact: CandidateStatusDefinition("Холодный контакт", "Поиск", "Контакт ещё не установлен", "Связаться с кандидатом"),
    CandidateStatus.not_suitable: CandidateStatusDefinition("Не подходит", "Первичный отбор", "Завершён: кандидат не подходит", "При необходимости вернуть в подбор"),
    CandidateStatus.refused: CandidateStatusDefinition("Кандидат отказался", "Подбор завершён", "Архив: отказ кандидата", "При необходимости вернуть в подбор"),
    CandidateStatus.applied: CandidateStatusDefinition("Отклик получен", "Первичный отбор", "Ожидает рассмотрения", "Провести первичный разбор"),
    CandidateStatus.test_sent: CandidateStatusDefinition("Тест отправлен", "Тестирование", "Ожидается результат", "Дождаться результата теста"),
    CandidateStatus.test_failed: CandidateStatusDefinition("Тест не пройден", "Тестирование", "Результат: не пройден", "Вернуть в подбор или завершить рассмотрение"),
    CandidateStatus.test_passed: CandidateStatusDefinition("Тест пройден", "Тестирование", "Результат: пройден", "Назначить собеседование"),
    CandidateStatus.interview: CandidateStatusDefinition("Собеседование", "Собеседование", "В работе", "Провести собеседование и зафиксировать решение"),
    CandidateStatus.consider: CandidateStatusDefinition("На рассмотрении", "Принятие решения", "Решение отложено", "Вернуться к решению по кандидату"),
    CandidateStatus.offer_accepted: CandidateStatusDefinition("Оффер принят", "Оформление", "Оффер принят кандидатом", "Запросить документы для трудоустройства"),
    CandidateStatus.full_documents: CandidateStatusDefinition("Полный пакет документов", "Оформление", "Документы собраны", "Подтвердить выход на работу"),
    CandidateStatus.rejection: CandidateStatusDefinition("Отказ работодателя", "Подбор завершён", "Архив: отказ работодателя", "При необходимости вернуть в подбор"),
    CandidateStatus.started_work: CandidateStatusDefinition("Вышел на работу", "Трудоустройство", "Сотрудник работает", "Сопровождать сотрудника"),
    CandidateStatus.resigned: CandidateStatusDefinition("Уволился", "Трудоустройство", "Архив: сотрудник уволился", "Карточка завершена"),
}


ALLOWED_STATUS_TRANSITIONS: dict[CandidateStatus, frozenset[CandidateStatus]] = {
    CandidateStatus.cold_contact: frozenset({CandidateStatus.applied, CandidateStatus.not_suitable, CandidateStatus.refused}),
    CandidateStatus.applied: frozenset({CandidateStatus.test_sent, CandidateStatus.interview, CandidateStatus.consider, CandidateStatus.not_suitable, CandidateStatus.refused, CandidateStatus.rejection}),
    CandidateStatus.test_sent: frozenset({CandidateStatus.test_failed, CandidateStatus.test_passed, CandidateStatus.refused, CandidateStatus.rejection}),
    CandidateStatus.test_failed: frozenset({CandidateStatus.applied}),
    CandidateStatus.test_passed: frozenset({CandidateStatus.consider, CandidateStatus.interview, CandidateStatus.refused, CandidateStatus.rejection}),
    CandidateStatus.consider: frozenset({CandidateStatus.test_sent, CandidateStatus.interview, CandidateStatus.offer_accepted, CandidateStatus.refused, CandidateStatus.rejection}),
    CandidateStatus.interview: frozenset({CandidateStatus.consider, CandidateStatus.offer_accepted, CandidateStatus.started_work, CandidateStatus.refused, CandidateStatus.rejection}),
    CandidateStatus.offer_accepted: frozenset({CandidateStatus.full_documents, CandidateStatus.started_work, CandidateStatus.refused, CandidateStatus.rejection}),
    CandidateStatus.full_documents: frozenset({CandidateStatus.started_work, CandidateStatus.refused, CandidateStatus.rejection}),
    CandidateStatus.started_work: frozenset({CandidateStatus.resigned}),
    CandidateStatus.not_suitable: frozenset({CandidateStatus.applied}),
    CandidateStatus.refused: frozenset({CandidateStatus.applied}),
    CandidateStatus.rejection: frozenset({CandidateStatus.applied}),
    CandidateStatus.resigned: frozenset(),
}


def allowed_transitions(status: CandidateStatus) -> frozenset[CandidateStatus]:
    return ALLOWED_STATUS_TRANSITIONS.get(status, frozenset())


def validate_status_transition(current: CandidateStatus | str, target: CandidateStatus | str) -> None:
    current_status = current if isinstance(current, CandidateStatus) else CandidateStatus(current)
    target_status = target if isinstance(target, CandidateStatus) else CandidateStatus(target)
    if current_status == target_status:
        return
    if target_status not in allowed_transitions(current_status):
        raise ValueError(
            f"Недопустимый переход: «{STATUS_DEFINITIONS[current_status].label}» → "
            f"«{STATUS_DEFINITIONS[target_status].label}»"
        )


def status_catalog_item(status: CandidateStatus) -> dict:
    definition = STATUS_DEFINITIONS[status]
    return {
        "status": status.value,
        "label": definition.label,
        "stage": definition.stage,
        "state": definition.state,
        "next_action": definition.next_action,
        "allowed_transitions": [item.value for item in allowed_transitions(status)],
    }
