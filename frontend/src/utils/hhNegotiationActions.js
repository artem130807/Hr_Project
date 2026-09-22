/**
 * Labels / helpers for HH negotiation actions (safe DTO from backend).
 */

export const HH_ACTION_LABELS = {
    discard: 'Отказ',
    consider: 'На рассмотрении',
    phone_interview: 'Телефонное интервью',
    interview: 'Пригласить на собеседование',
    assessment: 'Оценка / тестовое',
    offer: 'Предложение о работе',
    hired: 'Выход на работу',
};

export function hhActionLabel(action) {
    if (!action) return '';
    if (action.name && action.name !== action.id) return action.name;
    return HH_ACTION_LABELS[action.id] || action.name || action.id || '';
}

export function actionNeedsMessage(action) {
    const args = action?.arguments || [];
    return args.some((a) => a?.id === 'message');
}

export function enabledActions(actions) {
    return (actions || []).filter((a) => a && a.enabled && a.id);
}

export function actionButtonVariant(actionId) {
    if (actionId === 'discard') return 'danger';
    if (actionId === 'hired' || actionId === 'offer') return 'success';
    return 'primary';
}
