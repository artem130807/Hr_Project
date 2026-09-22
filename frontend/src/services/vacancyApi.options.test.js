/**
 * @jest-environment jsdom
 */
import { getVacancyOptions } from './vacancyApi';
import { http } from '../utils/http';

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
        patch: jest.fn(),
        put: jest.fn(),
        del: jest.fn(),
    },
}));

describe('getVacancyOptions', () => {
    beforeEach(() => {
        http.get.mockReset();
    });

    it('uses /vacancies/options when available', async () => {
        http.get.mockResolvedValueOnce([{ id: 1, name: 'A', hh_vacancy_id: '9' }]);
        const rows = await getVacancyOptions({ hhOnly: true });
        expect(http.get).toHaveBeenCalledWith('/vacancies/options?hh_only=true', expect.any(Object));
        expect(rows).toHaveLength(1);
        expect(rows[0].name).toBe('A');
    });

    it('falls back to /vacancies/published on failure (never full /vacancies)', async () => {
        http.get
            .mockRejectedValueOnce(new Error('Not Found'))
            .mockResolvedValueOnce([
                { id: 2, name: 'HH Job', hh_vacancy_id: '77', hh_vacancy_url: 'https://hh.ru/x' },
            ]);
        const rows = await getVacancyOptions({ hhOnly: false });
        expect(http.get.mock.calls[0][0]).toContain('/vacancies/options');
        expect(http.get.mock.calls[1][0]).toBe('/vacancies/published');
        expect(http.get.mock.calls.every((c) => c[0] !== '/vacancies')).toBe(true);
        expect(rows[0].id).toBe(2);
    });
});
