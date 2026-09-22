import { mapCandidateFromBackend, relationVacancyName, formatHhFullName } from './candidateMapper';

describe('candidateMapper', () => {
    it('maps current_status and last vacancy fields from backend list payload', () => {
        const mapped = mapCandidateFromBackend({
            id: 1,
            full_name: 'Ivan',
            current_status: 'откликнулся',
            last_vacancy_id: 9,
            last_vacancy_title: 'Механик',
            gender: 'male',
            total_work_expirience: 'between1And3',
        });

        expect(mapped.status).toBe('откликнулся');
        expect(mapped.vacancy_id).toBe(9);
        expect(mapped.vacancy_name).toBe('Механик');
        expect(mapped.gender).toBe('мужчина');
        expect(mapped.total_work_expirience).toBe('1-3 года');
    });

    it('normalizes telegram username from contacts', () => {
        expect(mapCandidateFromBackend({ telegram_username: 'nickname' }).telegram_username).toBe('@nickname');
        expect(mapCandidateFromBackend({ telegram_username: '@nick' }).telegram_username).toBe('@nick');
        expect(mapCandidateFromBackend({ telegram_username: 'https://t.me/nick' }).telegram_username).toBe('@nick');
        expect(mapCandidateFromBackend({ email: '  User@Mail.RU ' }).email).toBe('user@mail.ru');
    });

    it('relationVacancyName reads nested vacancy.name', () => {
        expect(relationVacancyName({ vacancy: { name: 'Водитель' }, vacancy_id: 2 })).toBe('Водитель');
        expect(relationVacancyName({ name: 'Прямое имя' })).toBe('Прямое имя');
        expect(relationVacancyName(null)).toBeNull();
    });

    it('formatHhFullName uses last-first-middle order', () => {
        expect(formatHhFullName({
            first_name: 'Артём',
            last_name: 'Сергеев',
            middle_name: 'Валерьевич',
        })).toBe('Сергеев Артём Валерьевич');
        expect(mapCandidateFromBackend({
            first_name: 'Иван',
            last_name: 'Иванов',
            middle_name: 'Иванович',
        }).full_name).toBe('Иванов Иван Иванович');
    });
});
