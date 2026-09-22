/**
 * @jest-environment jsdom
 */
import { getHRAvailability, createAvailability } from './sheduleApi';

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(() => Promise.resolve([])),
        post: jest.fn(() => Promise.resolve([])),
    },
}));

const { http } = require('../utils/http');

describe('sheduleApi', () => {
    beforeEach(() => {
        http.get.mockClear();
        http.post.mockClear();
    });

    it('encodes hr id in availability URL and forwards opts', async () => {
        const ac = new AbortController();
        await getHRAvailability('a1b2-c3/d4', '2026-08-17', '2026-08-23', { signal: ac.signal });
        expect(http.get).toHaveBeenCalledWith(
            '/availability/hr/a1b2-c3%2Fd4?date_from=2026-08-17&date_to=2026-08-23',
            { signal: ac.signal }
        );
    });

    it('trims hr_id on create', async () => {
        await createAvailability({
            hr_id: '  uuid-1  ',
            date: '2026-08-17',
            start_time: '10:00:00',
            end_time: '11:00:00',
            slot_length_minutes: 60,
        });
        expect(http.post).toHaveBeenCalledWith(
            '/availability/hr',
            expect.objectContaining({ hr_id: 'uuid-1' }),
            expect.any(Object)
        );
    });
});
