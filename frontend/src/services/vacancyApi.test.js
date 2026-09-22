import { formatDetail } from './vacancyApi';

jest.mock('../config/api', () => ({
    API_URL: 'http://api.test',
    API_PREFIX: '/v1',
    HH_API_URL: 'http://api.test',
}));

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
        patch: jest.fn(),
        del: jest.fn(),
        put: jest.fn(),
    },
}));

describe('vacancyApi HH sync helpers', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.post.mockReset();
        http.patch.mockReset();
        http.del.mockReset();
        http.put.mockReset();
    });

    it('formatDetail joins FastAPI validation arrays', () => {
        expect(formatDetail([{ msg: 'too short' }, { msg: 'required' }], 'x'))
            .toBe('too short; required');
    });

    it('updateVacancy maps server hh_synced=true', async () => {
        const { http } = require('../utils/http');
        http.patch.mockResolvedValue({
            id: 5,
            hh_vacancy_id: '99',
            name: 'Dev',
            hh_vacancy_url: 'https://hh.ru/vacancy/99',
            hh_synced: true,
        });

        const { updateVacancy } = require('./vacancyApi');
        const result = await updateVacancy(5, { name: 'Dev' });

        expect(http.patch).toHaveBeenCalledWith('/vacancy/5', { name: 'Dev' });
        expect(http.put).not.toHaveBeenCalled();
        expect(result._hhSynced).toBe(true);
    });

    it('updateVacancy maps soft HH sync failure from server', async () => {
        const { http } = require('../utils/http');
        http.patch.mockResolvedValue({
            id: 5,
            hh_vacancy_id: '99',
            name: 'Dev',
            hh_synced: false,
            hh_sync_error: 'HH down',
        });

        const { updateVacancy } = require('./vacancyApi');
        const result = await updateVacancy(5, { name: 'Dev' });

        expect(result._hhSynced).toBe(false);
        expect(result._hhSyncError).toBe('HH down');
        expect(http.put).not.toHaveBeenCalled();
    });

    it('updateVacancy does not pretend synced when only hh_vacancy_id is present', async () => {
        const { http } = require('../utils/http');
        http.patch.mockResolvedValue({ id: 5, hh_vacancy_id: '99', name: 'Dev' });

        const { updateVacancy } = require('./vacancyApi');
        const result = await updateVacancy(5, { name: 'Dev' });

        expect(result._hhSynced).toBe(false);
        expect(http.put).not.toHaveBeenCalled();
    });

    it('updateVacancy can force extra HH PUT when syncHH=true', async () => {
        const { http } = require('../utils/http');
        http.patch.mockResolvedValue({ id: 5, hh_vacancy_id: '99', name: 'Dev' });
        http.put.mockResolvedValue({ status: 'ok', hh_vacancy_id: '99', alternate_url: 'https://hh.ru/vacancy/99' });

        const { updateVacancy } = require('./vacancyApi');
        const result = await updateVacancy(5, { name: 'Dev' }, { syncHH: true });

        expect(http.put).toHaveBeenCalledWith('/vacancy/5/hh', {});
        expect(result._hhSynced).toBe(true);
        expect(result.hh_vacancy_url).toBe('https://hh.ru/vacancy/99');
    });

    it('deleteVacancy never changes the independent HH publication', async () => {
        const { http } = require('../utils/http');
        http.del.mockResolvedValue(null);

        const { deleteVacancy } = require('./vacancyApi');
        const result = await deleteVacancy(7, { removeFromHH: true, hasHHPublication: true });

        expect(http.del).toHaveBeenCalledTimes(1);
        expect(http.del).toHaveBeenCalledWith('/vacancy/7');
        expect(result.ok).toBe(true);
        expect(result.hhWarning).toBeUndefined();
    });

    it('deleteVacancy skips HH remove when not published', async () => {
        const { http } = require('../utils/http');
        http.del.mockResolvedValue(null);

        const { deleteVacancy } = require('./vacancyApi');
        await deleteVacancy(7, { removeFromHH: true, hasHHPublication: false });

        expect(http.del).toHaveBeenCalledTimes(1);
        expect(http.del).toHaveBeenCalledWith('/vacancy/7');
    });

    it('deleteVacancy requires id', async () => {
        const { deleteVacancy } = require('./vacancyApi');
        await expect(deleteVacancy(undefined)).rejects.toThrow(/Vacancy ID/i);
    });

    it('postVacancyToHH posts via database-service proxy', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ status: 'ok', hh_vacancy_id: '1' });

        const { postVacancyToHH } = require('./vacancyApi');
        const result = await postVacancyToHH(3);

        expect(http.post).toHaveBeenCalledWith('/vacancy/3/hh', {});
        expect(result.hh_vacancy_id).toBe('1');
    });

    it('makeVacancyTemplate posts to make-template endpoint', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ id: 42, is_template: true, public_code: 'В-42' });

        const { makeVacancyTemplate } = require('./vacancyApi');
        const result = await makeVacancyTemplate(9);

        expect(http.post).toHaveBeenCalledWith('/vacancy/9/make-template', {});
        expect(result.is_template).toBe(true);
        expect(result.public_code).toBe('В-42');
    });

    it('generateVacancyDescriptionAndSalary posts to HR AI orchestrator', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ description: 'text', salary_from: 100000, salary_to: 150000 });

        const { generateVacancyDescriptionAndSalary } = require('./vacancyApi');
        const result = await generateVacancyDescriptionAndSalary(8);

        expect(http.post).toHaveBeenCalledWith('/vacancy/8/description-salary-combine');
        expect(result.salary_from).toBe(100000);
    });
});
