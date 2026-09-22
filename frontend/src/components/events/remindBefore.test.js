/**
 * @jest-environment node
 */
const { normalizeRemindBefore } = require('./remindBefore');

describe('normalizeRemindBefore', () => {
    it('keeps 0 (notify on event day)', () => {
        expect(normalizeRemindBefore(0)).toBe(0);
        expect(normalizeRemindBefore('0')).toBe(0);
    });

    it('keeps positive integers', () => {
        expect(normalizeRemindBefore(3)).toBe(3);
        expect(normalizeRemindBefore('7')).toBe(7);
    });

    it('falls back for empty/invalid', () => {
        expect(normalizeRemindBefore('')).toBe(3);
        expect(normalizeRemindBefore(null)).toBe(3);
        expect(normalizeRemindBefore(undefined)).toBe(3);
        expect(normalizeRemindBefore(-1)).toBe(3);
        expect(normalizeRemindBefore('x')).toBe(3);
    });
});
