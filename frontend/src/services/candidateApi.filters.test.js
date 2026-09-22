/**
 * @jest-environment jsdom
 */
import { getCandidates } from './candidateApi';

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(() => Promise.resolve({ items: [], total: 0, page: 1, per_page: 50, total_pages: 0 })),
    },
}));

const { http } = require('../utils/http');

describe('getCandidates vacancy multi-filter + signal', () => {
    beforeEach(() => {
        http.get.mockClear();
    });

    it('appends repeated vacancy_id for checkbox multi-select', async () => {
        await getCandidates(null, null, null, [3, 9], undefined, 0, 20, 'candidate');
        const url = http.get.mock.calls[0][0];
        expect(url).toContain('vacancy_id=3');
        expect(url).toContain('vacancy_id=9');
        expect(url).toContain('category=candidate');
        expect(url).toContain('per_page=20');
    });

    it('forwards AbortSignal in opts', async () => {
        const ac = new AbortController();
        await getCandidates(null, 'Иван', null, null, undefined, 0, 20, null, { signal: ac.signal });
        expect(http.get).toHaveBeenCalledWith(
            expect.stringContaining('search='),
            expect.objectContaining({ signal: ac.signal })
        );
    });
});
