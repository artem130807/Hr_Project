jest.mock('../config/api', () => ({
    API_URL: 'http://api.test',
    API_PREFIX: '/v1',
}));

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
        patch: jest.fn(),
        put: jest.fn(),
        del: jest.fn(),
    },
}));

describe('vacancyFilterApi', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.post.mockReset();
        http.patch.mockReset();
        http.put.mockReset();
        http.del.mockReset();
    });

    it('listVacancyFilters GETs /vacancy-filters', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([{ id: 1, city: 'Москва' }]);
        const { listVacancyFilters } = require('./vacancyFilterApi');

        const result = await listVacancyFilters();
        expect(http.get).toHaveBeenCalledWith('/vacancy-filters');
        expect(result).toEqual([{ id: 1, city: 'Москва' }]);
    });

    it('createVacancyFilter POSTs payload', async () => {
        const { http } = require('../utils/http');
        const payload = { city: 'Казань', work_format: 'remote' };
        http.post.mockResolvedValue({ id: 2, ...payload });
        const { createVacancyFilter } = require('./vacancyFilterApi');

        const result = await createVacancyFilter(payload);
        expect(http.post).toHaveBeenCalledWith('/vacancy-filters', payload);
        expect(result.id).toBe(2);
    });

    it('assignFilterToVacancy PUTs link', async () => {
        const { http } = require('../utils/http');
        http.put.mockResolvedValue({ id: 10, filter_id: 3 });
        const { assignFilterToVacancy } = require('./vacancyFilterApi');

        const result = await assignFilterToVacancy(10, 3);
        expect(http.put).toHaveBeenCalledWith('/vacancy/10/filter/3');
        expect(result.filter_id).toBe(3);
    });

    it('unassignFilterFromVacancy DELETEs link', async () => {
        const { http } = require('../utils/http');
        http.del.mockResolvedValue({ id: 10, filter_id: null });
        const { unassignFilterFromVacancy } = require('./vacancyFilterApi');

        await unassignFilterFromVacancy(10);
        expect(http.del).toHaveBeenCalledWith('/vacancy/10/filter');
    });

    it('runVacancyFilterNow POSTs run-filter', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({
            status: 'ok',
            summary: { rejected: 2, checked: 5 },
        });
        const { runVacancyFilterNow } = require('./vacancyFilterApi');

        const result = await runVacancyFilterNow(42);
        expect(http.post).toHaveBeenCalledWith('/vacancy/42/run-filter', {});
        expect(result.summary.rejected).toBe(2);
    });

    it('getVacancyFilter GETs by id', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ id: 5, city: 'Уфа' });
        const { getVacancyFilter } = require('./vacancyFilterApi');

        const result = await getVacancyFilter(5);
        expect(http.get).toHaveBeenCalledWith('/vacancy-filters/5');
        expect(result.city).toBe('Уфа');
    });

    it('updateVacancyFilter PATCHes by id', async () => {
        const { http } = require('../utils/http');
        http.patch.mockResolvedValue({ id: 5, city: 'Сочи' });
        const { updateVacancyFilter } = require('./vacancyFilterApi');

        const result = await updateVacancyFilter(5, { city: 'Сочи' });
        expect(http.patch).toHaveBeenCalledWith('/vacancy-filters/5', { city: 'Сочи' });
        expect(result.city).toBe('Сочи');
    });

    it('deleteVacancyFilter DELETEs by id', async () => {
        const { http } = require('../utils/http');
        http.del.mockResolvedValue(null);
        const { deleteVacancyFilter } = require('./vacancyFilterApi');

        await deleteVacancyFilter(5);
        expect(http.del).toHaveBeenCalledWith('/vacancy-filters/5');
    });

    it('formatFilterRunSummary explains batch cap', () => {
        const { formatFilterRunSummary } = require('./vacancyFilterApi');
        const { msg, level } = formatFilterRunSummary({
            checked: 8,
            matched: 3,
            rejected: 5,
            errors: 0,
            batch_capped: true,
            batch_size: 5,
            interval_minutes: 10,
        });
        expect(level).toBe('success');
        expect(msg).toMatch(/отказов «не подходит» 5/);
        expect(msg).toMatch(/каждые 10 мин/);
    });
});
