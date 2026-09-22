/**
 * @jest-environment node
 */
jest.mock('../utils/http', () => ({
    http: { get: jest.fn(), post: jest.fn() },
    refreshSession: jest.fn(() => Promise.resolve(false)),
}));
jest.mock('../utils/tokenStorage', () => ({
    getAccessToken: jest.fn(() => 'tok'),
}));
jest.mock('../config/api', () => ({
    API_URL: 'http://api.test',
    API_PREFIX: '/v1',
}));

const { http } = require('../utils/http');
const { checkHHAuth, getHHAuthLink } = require('./hhAuthApi');

describe('hhAuthApi via DB proxy', () => {
    beforeEach(() => {
        http.get.mockReset();
        global.fetch = jest.fn();
    });

    it('checkHHAuth uses /hh-oauth/status', async () => {
        http.get.mockResolvedValue({ auth_passed: true });
        const result = await checkHHAuth();
        expect(http.get).toHaveBeenCalledWith('/hh-oauth/status');
        expect(result.auth_passed).toBe(true);
    });

    it('getHHAuthLink fetches /v1/hh-oauth/login-url', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            status: 200,
            text: async () => '"https://hh.ru/oauth/authorize?x=1"',
            json: async () => ({}),
        });
        const link = await getHHAuthLink();
        expect(global.fetch).toHaveBeenCalledWith(
            'http://api.test/v1/hh-oauth/login-url',
            expect.objectContaining({ method: 'GET' })
        );
        expect(link).toBe('https://hh.ru/oauth/authorize?x=1');
    });
});
