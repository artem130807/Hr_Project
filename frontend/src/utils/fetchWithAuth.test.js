import { fetchWithAuth } from './fetchWithAuth';
import { resetAuthClearedFlag } from './http';

const storage = new Map();

global.fetch = jest.fn();

describe('fetchWithAuth', () => {
    beforeEach(() => {
        fetch.mockClear();
        storage.clear();
        resetAuthClearedFlag();

        jest.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => (
            storage.has(key) ? storage.get(key) : null
        ));
        jest.spyOn(Storage.prototype, 'setItem').mockImplementation((key, value) => {
            storage.set(String(key), String(value));
        });
        jest.spyOn(Storage.prototype, 'removeItem').mockImplementation((key) => {
            storage.delete(String(key));
        });
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    it('retries once after silent refresh on 401', async () => {
        storage.set('token', 'old');
        storage.set('refresh_token', 'r1');

        fetch
            .mockResolvedValueOnce({
                ok: false,
                status: 401,
                text: async () => 'Unauthorized',
            })
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({
                    access_token: 'new',
                    refresh_token: 'r2',
                    expires: '2026-01-01T00:30:00Z',
                    token_type: 'bearer',
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ ok: true }),
                json: async () => ({ ok: true }),
            });

        const res = await fetchWithAuth('https://example.test/v1/x', { method: 'GET' });
        expect(res.status).toBe(200);
        expect(storage.get('token')).toBe('new');
        expect(fetch).toHaveBeenCalledTimes(3);
    });
});
