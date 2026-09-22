/**
 * @jest-environment node
 */
jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
    },
}));

describe('publicProfessionalTestApi', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.post.mockReset();
    });

    it('loads public Q&A test without auth', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ id: 10, questions: [] });
        const { getPublicProfessionalTest } = require('./publicProfessionalTestApi');
        await getPublicProfessionalTest(10);
        expect(http.get).toHaveBeenCalledWith('/public/tests/10', { auth: false });
    });

    it('submits public result without auth', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ id: 1 });
        const { submitPublicProfessionalResult } = require('./publicProfessionalTestApi');
        const body = {
            test_id: 10,
            full_name: 'A',
            position: 'B',
            taken_at: '2026-08-14',
            answers: { 1: 'ответ' },
        };
        await submitPublicProfessionalResult(body);
        expect(http.post).toHaveBeenCalledWith('/public/tests/results', body, { auth: false });
    });

    it('lists HR results with FIO and specialty filters', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([]);
        const { listPublicProfessionalResults } = require('./publicProfessionalTestApi');
        await listPublicProfessionalResults({ q: 'Иванов', position: 'Логист' });
        expect(http.get).toHaveBeenCalledWith(
            '/public-test-results?q=%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2&position=%D0%9B%D0%BE%D0%B3%D0%B8%D1%81%D1%82'
        );
    });
});
