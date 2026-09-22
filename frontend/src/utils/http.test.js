import { request, http, resetAuthClearedFlag, refreshSession } from './http';
import { API_URL, API_PREFIX } from '../config/api';

const storage = new Map();

global.fetch = jest.fn();

describe('http utils', () => {
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
        jest.spyOn(Storage.prototype, 'clear').mockImplementation(() => {
            storage.clear();
        });

        delete window.location;
        window.location = {
            replace: jest.fn(),
            pathname: '/tests',
        };
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    describe('request function', () => {
        it('должен делать GET запрос с токеном авторизации', async () => {
            storage.set('token', 'test-token-123');
            const mockResponse = { data: 'test' };

            fetch.mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify(mockResponse),
            });

            const result = await request('/test-path', { auth: true });

            expect(fetch).toHaveBeenCalledWith(
                `${API_URL}${API_PREFIX}/test-path`,
                expect.objectContaining({
                    method: 'GET',
                    headers: expect.objectContaining({
                        Authorization: 'Bearer test-token-123',
                    }),
                })
            );
            expect(result).toEqual(mockResponse);
        });

        it('должен передавать X-Actor заголовки из сохранённого пользователя', async () => {
            storage.set('token', 'test-token-123');
            storage.set('user', JSON.stringify({
                erp_user_id: 'u-9',
                full_name: 'Анна Смирнова',
            }));

            fetch.mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ ok: true }),
            });

            await request('/candidate/1/status', { auth: true, method: 'PUT', body: { status: 'собес' } });

            expect(fetch).toHaveBeenCalledWith(
                `${API_URL}${API_PREFIX}/candidate/1/status`,
                expect.objectContaining({
                    headers: expect.objectContaining({
                        Authorization: 'Bearer test-token-123',
                        'X-Actor-Id': 'u-9',
                        'X-Actor-Name': encodeURIComponent('Анна Смирнова'),
                    }),
                })
            );
        });

        it('должен делать запрос без токена если auth = false', async () => {
            fetch.mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ data: 'test' }),
            });

            await request('/test-path', { auth: false });

            const fetchCall = fetch.mock.calls[0];
            expect(fetchCall[1].headers.Authorization).toBeUndefined();
        });

        it('должен отправлять JSON body', async () => {
            const mockBody = { name: 'test', value: 123 };

            fetch.mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ success: true }),
            });

            await request('/test-path', {
                method: 'POST',
                body: mockBody,
                auth: false,
            });

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify(mockBody),
                    headers: expect.objectContaining({
                        'Content-Type': 'application/json',
                    }),
                })
            );
        });

        it('должен отправлять FormData без изменения Content-Type', async () => {
            const formData = new FormData();
            formData.append('file', 'test');

            fetch.mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ success: true }),
            });

            await request('/test-path', {
                method: 'POST',
                body: formData,
                auth: false,
            });

            const fetchCall = fetch.mock.calls[0];
            expect(fetchCall[1].body).toBe(formData);
            expect(fetchCall[1].headers['Content-Type']).toBeUndefined();
        });

        it('должен отправлять URLSearchParams без изменения', async () => {
            const params = new URLSearchParams();
            params.append('key', 'value');

            fetch.mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ success: true }),
            });

            await request('/test-path', {
                method: 'POST',
                body: params,
                auth: false,
            });

            const fetchCall = fetch.mock.calls[0];
            expect(fetchCall[1].body).toBe(params);
        });

        it('должен обрабатывать 401 ошибку и редиректить на логин', async () => {
            storage.set('token', 'test-token-123');
            // no refresh_token → immediate logout

            fetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                text: async () => 'Unauthorized',
            });

            await expect(request('/test-path')).rejects.toThrow('Unauthorized');

            expect(Storage.prototype.removeItem).toHaveBeenCalledWith('token');
            expect(window.location.replace).toHaveBeenCalledWith('/');
        });

        it('при 401 обновляет access через refresh и повторяет запрос', async () => {
            storage.set('token', 'old-access');
            storage.set('refresh_token', 'valid-refresh');

            fetch
                .mockResolvedValueOnce({
                    ok: false,
                    status: 401,
                    text: async () => JSON.stringify({ detail: 'Token has expired' }),
                })
                .mockResolvedValueOnce({
                    ok: true,
                    status: 200,
                    text: async () => JSON.stringify({
                        access_token: 'new-access',
                        refresh_token: 'new-refresh',
                        expires: '2026-01-01T00:30:00Z',
                        refresh_expires: '2026-01-15T00:00:00Z',
                        token_type: 'bearer',
                    }),
                })
                .mockResolvedValueOnce({
                    ok: true,
                    status: 200,
                    text: async () => JSON.stringify({ ok: true }),
                });

            const result = await request('/secure');

            expect(result).toEqual({ ok: true });
            expect(storage.get('token')).toBe('new-access');
            expect(storage.get('refresh_token')).toBe('new-refresh');
            expect(window.location.replace).not.toHaveBeenCalled();
            // original + refresh + retry
            expect(fetch).toHaveBeenCalledTimes(3);
            expect(fetch.mock.calls[1][0]).toContain('/token/refresh');
            expect(fetch.mock.calls[2][1].headers.Authorization).toBe('Bearer new-access');
        });

        it('при неудачном refresh выходит из сессии', async () => {
            storage.set('token', 'old-access');
            storage.set('refresh_token', 'bad-refresh');

            fetch
                .mockResolvedValueOnce({
                    ok: false,
                    status: 401,
                    text: async () => JSON.stringify({ detail: 'Token has expired' }),
                })
                .mockResolvedValueOnce({
                    ok: false,
                    status: 401,
                    text: async () => JSON.stringify({ detail: 'Invalid refresh token' }),
                });

            await expect(request('/secure')).rejects.toThrow(/Token has expired|Unauthorized/i);
            expect(storage.has('token')).toBe(false);
            expect(storage.has('refresh_token')).toBe(false);
            expect(window.location.replace).toHaveBeenCalledWith('/');
        });

        it('после успешного refresh второй 401 не сносит HR-сессию', async () => {
            storage.set('token', 'old-access');
            storage.set('refresh_token', 'valid-refresh');

            fetch
                .mockResolvedValueOnce({
                    ok: false,
                    status: 401,
                    text: async () => JSON.stringify({ detail: 'Token has expired' }),
                })
                .mockResolvedValueOnce({
                    ok: true,
                    status: 200,
                    text: async () => JSON.stringify({
                        access_token: 'new-access',
                        refresh_token: 'new-refresh',
                        expires: '2026-01-01T00:30:00Z',
                        token_type: 'bearer',
                    }),
                })
                .mockResolvedValueOnce({
                    ok: false,
                    status: 401,
                    text: async () => JSON.stringify({ detail: 'Forbidden for this resource' }),
                });

            await expect(request('/secure')).rejects.toThrow(/Forbidden for this resource/i);
            expect(storage.get('token')).toBe('new-access');
            expect(storage.get('refresh_token')).toBe('new-refresh');
            expect(window.location.replace).not.toHaveBeenCalled();
        });

        it('refreshSession считает успехом ротацию из другой вкладки', async () => {
            storage.set('refresh_token', 'r1');
            storage.set('token', 'old');

            fetch.mockImplementationOnce(async () => {
                storage.set('refresh_token', 'r2');
                storage.set('token', 'new-from-other-tab');
                return {
                    ok: false,
                    status: 401,
                    text: async () => JSON.stringify({ detail: 'Refresh token already rotated' }),
                };
            });

            await expect(refreshSession()).resolves.toBe(true);
            expect(storage.get('token')).toBe('new-from-other-tab');
            expect(storage.get('refresh_token')).toBe('r2');
        });

        it('при 401 без access, но с refresh — обновляет сессию и повторяет запрос', async () => {
            storage.set('refresh_token', 'valid-refresh');
            // access token отсутствует

            fetch
                .mockResolvedValueOnce({
                    ok: false,
                    status: 401,
                    text: async () => JSON.stringify({ detail: 'Not authenticated' }),
                })
                .mockResolvedValueOnce({
                    ok: true,
                    status: 200,
                    text: async () => JSON.stringify({
                        access_token: 'new-access',
                        refresh_token: 'new-refresh',
                        expires: '2026-01-01T00:30:00Z',
                        refresh_expires: '2026-01-15T00:00:00Z',
                        token_type: 'bearer',
                    }),
                })
                .mockResolvedValueOnce({
                    ok: true,
                    status: 200,
                    text: async () => JSON.stringify({ ok: true }),
                });

            const result = await request('/secure');
            expect(result).toEqual({ ok: true });
            expect(storage.get('token')).toBe('new-access');
            expect(window.location.replace).not.toHaveBeenCalled();
        });

        it('не должен выкидывать на логин при 401 от HH OAuth', async () => {
            storage.set('token', 'test-token-123');

            fetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                text: async () => JSON.stringify({ detail: 'HH token invalid or revoked' }),
            });

            await expect(request('/vacancy/1/hh')).rejects.toThrow(/HH token/i);

            expect(Storage.prototype.removeItem).not.toHaveBeenCalledWith('token');
            expect(window.location.replace).not.toHaveBeenCalled();
        });

        it('не должен выкидывать на логин при 401 от AI-сервиса', async () => {
            storage.set('token', 'test-token-123');

            fetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                text: async () => JSON.stringify({
                    detail: 'AI service auth failed: Could not validate credentials',
                }),
            });

            await expect(request('/vacancy/12/description-salary-combine', { method: 'POST' }))
                .rejects.toThrow(/AI service auth/i);

            expect(Storage.prototype.removeItem).not.toHaveBeenCalledWith('token');
            expect(window.location.replace).not.toHaveBeenCalled();
        });

        it('должен понятно сообщать о Failed to fetch', async () => {
            // GET retries once on network blip — both attempts fail
            fetch
                .mockRejectedValueOnce(new TypeError('Failed to fetch'))
                .mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(request('/vacancy/1')).rejects.toThrow(/Нет связи с API/i);
        });

        it('должен понятно сообщать о Failed to fetch без retry для POST', async () => {
            fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

            await expect(request('/vacancy/1', { method: 'POST', body: {} })).rejects.toThrow(/Нет связи с API/i);
            expect(fetch).toHaveBeenCalledTimes(1);
        });

        it('не должен редиректить на логин если уже на странице логина', async () => {
            window.location.pathname = '/';
            storage.set('token', 'test-token-123');

            fetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                text: async () => 'Unauthorized',
            });

            await expect(request('/test-path')).rejects.toThrow('Unauthorized');

            expect(Storage.prototype.removeItem).toHaveBeenCalledWith('token');
            expect(window.location.replace).not.toHaveBeenCalled();
        });

        it('не должен сносить токен на 401 без токена в запросе', async () => {
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                text: async () => 'Unauthorized',
            });

            await expect(request('/test-path', { auth: false })).rejects.toThrow('Unauthorized');
            expect(Storage.prototype.removeItem).not.toHaveBeenCalledWith('token');
        });

        it('должен обрабатывать ошибки с JSON телом', async () => {
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                text: async () => JSON.stringify({ detail: 'Custom error message' }),
            });

            await expect(request('/test-path', { auth: false }))
                .rejects.toThrow('Custom error message');
        });

        it('должен обрабатывать ошибки с message в JSON', async () => {
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                text: async () => JSON.stringify({ message: 'Error via message field' }),
            });

            await expect(request('/test-path', { auth: false }))
                .rejects.toThrow('Error via message field');
        });

        it('должен возвращать пустой ответ если нет тела', async () => {
            fetch.mockResolvedValueOnce({
                ok: true,
                status: 204,
                text: async () => '',
            });

            const result = await request('/test-path', { auth: false });
            expect(result).toBeNull();
        });

        it('должен возвращать текст если ответ не JSON', async () => {
            fetch.mockResolvedValueOnce({
                ok: true,
                status: 200,
                text: async () => 'plain text response',
            });

            const result = await request('/test-path', { auth: false });
            expect(result).toBe('plain text response');
        });
    });

    describe('http helper methods', () => {
        beforeEach(() => {
            fetch.mockClear();
            storage.clear();
            resetAuthClearedFlag();
            fetch.mockResolvedValue({
                ok: true,
                status: 200,
                text: async () => JSON.stringify({ success: true }),
            });
        });

        it('http.get должен делать GET запрос', async () => {
            await http.get('/test');
            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({ method: 'GET' })
            );
        });

        it('http.post должен делать POST запрос с телом', async () => {
            const body = { test: 'data' };
            await http.post('/test', body);

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify(body),
                })
            );
        });

        it('http.put должен делать PUT запрос', async () => {
            await http.put('/test', { data: 'test' });
            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({ method: 'PUT' })
            );
        });

        it('http.patch должен делать PATCH запрос', async () => {
            await http.patch('/test', { data: 'test' });
            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({ method: 'PATCH' })
            );
        });

        it('http.del должен делать DELETE запрос', async () => {
            await http.del('/test');
            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({ method: 'DELETE' })
            );
        });
    });
});
