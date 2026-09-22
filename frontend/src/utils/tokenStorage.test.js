import {
    getAccessToken,
    getRefreshToken,
    setSessionTokens,
    clearSession,
    setStoredUser,
    getStoredUser,
    isAccessTokenExpired,
    getAccessTokenPayload,
    TOKEN_KEYS,
} from './tokenStorage';

const storage = new Map();

describe('tokenStorage', () => {
    beforeEach(() => {
        storage.clear();
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

    it('stores access and refresh tokens from AuthResponse', () => {
        setSessionTokens({
            access_token: 'access-1',
            refresh_token: 'refresh-1',
            expires: '2026-01-01T00:00:00Z',
            refresh_expires: '2026-01-15T00:00:00Z',
            token_type: 'bearer',
        });

        expect(getAccessToken()).toBe('access-1');
        expect(getRefreshToken()).toBe('refresh-1');
        expect(storage.get(TOKEN_KEYS.ACCESS_EXPIRES_KEY)).toBe('2026-01-01T00:00:00Z');
        expect(storage.get(TOKEN_KEYS.REFRESH_EXPIRES_KEY)).toBe('2026-01-15T00:00:00Z');
    });

    it('clears all session keys', () => {
        setSessionTokens({ access_token: 'a', refresh_token: 'r' });
        setStoredUser({ id: 1, name: 'Test' });
        clearSession();
        expect(getAccessToken()).toBeNull();
        expect(getRefreshToken()).toBeNull();
        expect(getStoredUser()).toBeNull();
    });

    it('round-trips user JSON', () => {
        setStoredUser({ id: 2, role: 'hr' });
        expect(getStoredUser()).toEqual({ id: 2, role: 'hr' });
    });

        it('isAccessTokenExpired uses stored expires with skew', () => {
        setSessionTokens({
            access_token: 'access-1',
            expires: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
        });
        expect(isAccessTokenExpired()).toBe(false);

        setSessionTokens({
            access_token: 'access-1',
            expires: new Date(Date.now() - 1000).toISOString(),
        });
        expect(isAccessTokenExpired()).toBe(true);
    });

    it('isAccessTokenExpired is true within skew window before expiry', () => {
        setSessionTokens({
            access_token: 'access-1',
            expires: new Date(Date.now() + 30 * 1000).toISOString(),
        });
        expect(isAccessTokenExpired(60)).toBe(true);
    });

    it('isAccessTokenExpired reads JWT exp when expires key missing', () => {
        const exp = Math.floor(Date.now() / 1000) + 600;
        const payload = btoa(JSON.stringify({ sub: 'u', exp }));
        const token = `hdr.${payload}.sig`;
        storage.set(TOKEN_KEYS.ACCESS_TOKEN_KEY, token);
        expect(isAccessTokenExpired()).toBe(false);
    });

    it('reads role_id from access token claims', () => {
        const payload = btoa(JSON.stringify({ sub: 'u', role_id: 7 }));
        storage.set(TOKEN_KEYS.ACCESS_TOKEN_KEY, `hdr.${payload}.sig`);
        expect(getAccessTokenPayload().role_id).toBe(7);
    });

    it('isAccessTokenExpired is true when access missing', () => {
        expect(isAccessTokenExpired()).toBe(true);
    });
});
