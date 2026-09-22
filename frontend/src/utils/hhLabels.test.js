import {
    scheduleLabel,
    employmentLabel,
    experienceLabel,
    genderLabel,
    labelFromDict,
    HH_SCHEDULE_LABELS,
} from './hhLabels';

describe('hhLabels', () => {
    it('переводит известные id графика на русский', () => {
        expect(scheduleLabel('flyInFlyOut')).toBe('Вахтовый метод');
        expect(scheduleLabel('fullDay')).toBe('Полный день');
        expect(scheduleLabel('remote')).toBe('Удалённая работа');
    });

    it('переводит занятость и опыт', () => {
        expect(employmentLabel('full')).toBe('Полная занятость');
        expect(employmentLabel('part')).toBe('Частичная занятость');
        expect(experienceLabel('moreThan6')).toBe('Более 6 лет');
        expect(experienceLabel('noExperience')).toBe('Нет опыта');
    });

    it('предпочитает имя из словаря HH', () => {
        const dict = { schedules: [{ id: 'flyInFlyOut', name: 'Вахта (из справочника)' }] };
        expect(scheduleLabel('flyInFlyOut', dict)).toBe('Вахта (из справочника)');
    });

    it('genderLabel переводит male/female', () => {
        expect(genderLabel('male')).toBe('мужчина');
        expect(genderLabel('female')).toBe('женщина');
    });

    it('labelFromDict возвращает пустую строку для пустого id', () => {
        expect(labelFromDict([], null, HH_SCHEDULE_LABELS)).toBe('');
        expect(labelFromDict([], '', HH_SCHEDULE_LABELS)).toBe('');
    });
});
