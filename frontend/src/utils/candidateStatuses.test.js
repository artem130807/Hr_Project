import {
    allowedStatusTransitions,
    candidateState,
    flattenStatusTree,
    isArchiveStatus,
    isHireStatus,
    statusLabel,
    statusNextAction,
    statusStage,
    statusState,
} from './candidateStatuses';

describe('candidateStatuses', () => {
    it('flattens hierarchy with depths', () => {
        const rows = flattenStatusTree();
        expect(rows.map((r) => r.value)).toEqual([
            'холодный контакт',
            'не подходит',
            'отказался',
            'откликнулся',
            'тест: отправлен',
            'тест: не прошли',
            'тест: пройден',
            'подумать',
            'собес',
            'отказ',
            'оффер принят',
            'Full documents',
            'ВНР',
            'уволился',
        ]);
        expect(rows.find((r) => r.value === 'уволился').depth).toBe(5);
    });

    it('detects archive and hire statuses', () => {
        expect(isArchiveStatus('отказ')).toBe(true);
        expect(isHireStatus('ВНР')).toBe(true);
        expect(isHireStatus('оффер принят')).toBe(false);
        expect(isArchiveStatus('собес')).toBe(false);
    });

    it('uses readable labels for funnel statuses', () => {
        expect(statusLabel('собес')).toBe('Собеседование');
        expect(statusLabel('подумать')).toBe('Подумать');
        expect(statusLabel('отказ')).toBe('Отказ');
        expect(statusLabel('Full documents')).toBe('Полный пакет документов');
    });

    it('separates stage, state and next action', () => {
        expect(candidateState('архивирован', 'отказ')).toBe('Архив: отказ работодателя');
        expect(candidateState('в процессе найма', 'собес')).toBe('В работе');
        expect(candidateState('нанят', 'ВНР')).toBe('Сотрудник работает');
        expect(statusStage('тест: не прошли')).toBe('Тестирование');
        expect(statusState('тест: не прошли', 'в процессе найма')).toBe('Результат: не пройден');
        expect(statusNextAction('Full documents')).toBe('Подтвердить выход на работу');
    });

    it('allows only explicit transitions and supports server catalog overrides', () => {
        expect(allowedStatusTransitions('оффер принят')).toEqual(
            expect.arrayContaining(['Full documents', 'ВНР', 'отказ'])
        );
        expect(allowedStatusTransitions('ВНР')).toEqual(['уволился']);
        expect(allowedStatusTransitions('отказ')).toEqual(['откликнулся']);
        expect(allowedStatusTransitions('собес', [{
            code: 'собес',
            allowedTransitions: ['подумать'],
        }])).toEqual(['подумать']);
    });
});
