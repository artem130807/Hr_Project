/**
 * @jest-environment jsdom
 */
import { mergeHhVacancyFilterOptions } from './hhVacancyFilterOptions';

describe('mergeHhVacancyFilterOptions', () => {
    it('keeps local HH-linked vacancies', () => {
        const { options, unboundHhCount } = mergeHhVacancyFilterOptions(
            [
                { id: 1, name: 'Local A', hh_vacancy_id: '10' },
                { id: 2, name: 'Local only', hh_vacancy_id: null },
            ],
            []
        );
        expect(options).toHaveLength(1);
        expect(options[0].id).toBe(1);
        expect(unboundHhCount).toBe(0);
    });

    it('adds HH items with local_vacancy_id and counts unbound', () => {
        const { options, unboundHhCount } = mergeHhVacancyFilterOptions(
            [],
            [
                { hh_vacancy_id: '10', name: 'From HH', local_vacancy_id: 5 },
                { hh_vacancy_id: '11', name: 'Unbound', local_vacancy_id: null, archived: false },
                { hh_vacancy_id: '12', name: 'Archived unbound', local_vacancy_id: null, archived: true },
            ]
        );
        expect(options).toEqual([
            expect.objectContaining({ id: 5, name: 'From HH', hh_vacancy_id: '10' }),
        ]);
        expect(unboundHhCount).toBe(1);
    });
});
