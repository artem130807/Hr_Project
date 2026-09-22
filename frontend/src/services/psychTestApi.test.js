/**
 * @jest-environment node
 */
jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
    },
}));

describe('psychTestApi', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.post.mockReset();
    });

    it('loads public instrument without auth', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ id: 'complex_work_behavior_220', items: [] });
        const { getPublicPsychInstrument } = require('./psychTestApi');
        await getPublicPsychInstrument('complex_work_behavior_220');
        expect(http.get).toHaveBeenCalledWith(
            '/public/psych/instruments/complex_work_behavior_220',
            { auth: false }
        );
    });

    it('submits public result without auth', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ id: 1 });
        const { submitPublicPsychResult } = require('./psychTestApi');
        const body = {
            instrument_id: 'complex_work_behavior_220',
            full_name: 'A',
            position: 'B',
            taken_at: '2026-08-14',
            answers: { 1: 3 },
        };
        await submitPublicPsychResult(body);
        expect(http.post).toHaveBeenCalledWith('/public/psych/results', body, { auth: false });
    });

    it('lists HR results with optional instrument filter', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([]);
        const { listPsychResults } = require('./psychTestApi');
        await listPsychResults({ instrument_id: 'complex_work_behavior_220' });
        expect(http.get).toHaveBeenCalledWith(
            '/psych/results?instrument_id=complex_work_behavior_220'
        );
    });
});
