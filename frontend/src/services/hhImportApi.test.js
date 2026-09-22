jest.mock('../config/api', () => ({
    API_URL: 'http://api.test',
    API_PREFIX: '/v1',
    HH_API_URL: 'http://api.test',
}));

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
    },
}));

describe('hhImportApi', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.post.mockReset();
    });

    it('getHHEmployerVacancies sends archived/page params', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ items: [], found: 0, page: 0, pages: 0 });

        const { getHHEmployerVacancies } = require('./hhImportApi');
        await getHHEmployerVacancies({ archived: true, page: 2, per_page: 20 });

        expect(http.get).toHaveBeenCalledWith(
            expect.stringMatching(/\/hh\/employer-vacancies\?/)
        );
        const url = http.get.mock.calls[0][0];
        expect(url).toContain('archived=true');
        expect(url).toContain('page=2');
        expect(url).toContain('per_page=20');
        expect(url).toContain('all_accessible=true');
    });

    it('linkHHVacancyToLocal posts local_vacancy_id query', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ status: 'ok', local_vacancy_id: 9, hh_vacancy_id: '55' });

        const { linkHHVacancyToLocal } = require('./hhImportApi');
        const result = await linkHHVacancyToLocal('55', 9);

        expect(http.post).toHaveBeenCalledWith(
            '/hh/vacancies/55/link?local_vacancy_id=9',
            {}
        );
        expect(result.hh_vacancy_id).toBe('55');
    });

    it('importHHVacancyToLocal posts department query', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({
            status: 'ok',
            created: true,
            local_vacancy_id: 12,
            hh_vacancy_id: '55',
        });

        const { importHHVacancyToLocal } = require('./hhImportApi');
        const result = await importHHVacancyToLocal('55', 'логистический');

        expect(http.post).toHaveBeenCalledWith(
            expect.stringMatching(/\/hh\/vacancies\/55\/import\?/),
            {}
        );
        const url = http.post.mock.calls[0][0];
        expect(url).toContain('department=');
        expect(decodeURIComponent(url)).toContain('логистический');
        expect(result.created).toBe(true);
    });

    it('getHHVacancyNegotiations encodes vacancy id', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ items: [] });

        const { getHHVacancyNegotiations } = require('./hhImportApi');
        await getHHVacancyNegotiations('12/34', { collection: 'response', page: 1 });

        const url = http.get.mock.calls[0][0];
        expect(url).toContain('/hh/vacancies/12%2F34/negotiations?');
        expect(url).toContain('collection=response');
        expect(url).toContain('page=1');
    });

    it('getHHNegotiationDetail encodes negotiation id', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ id: 'a/b', actions: [] });

        const { getHHNegotiationDetail } = require('./hhImportApi');
        await getHHNegotiationDetail('a/b');

        expect(http.get).toHaveBeenCalledWith('/hh/negotiations/a%2Fb');
    });

    it('executeHHNegotiationAction posts arguments body', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ status: 'ok', action_id: 'discard' });

        const { executeHHNegotiationAction } = require('./hhImportApi');
        await executeHHNegotiationAction('n1', 'discard', { arguments: { message: 'Нет' } });

        expect(http.post).toHaveBeenCalledWith(
            '/hh/negotiations/n1/actions/discard',
            { arguments: { message: 'Нет' } }
        );
    });
});
