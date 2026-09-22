/**
 * @jest-environment node
 */
import { interviewsWeekHint, PROFILE_METRIC_LABELS } from './profileMetrics';

describe('profileMetrics', () => {
    it('uses HR wording instead of logistics trips/revenue', () => {
        expect(PROFILE_METRIC_LABELS.interviews).toBe('Мои собеседования');
        expect(PROFILE_METRIC_LABELS.hired).toBe('Трудоустроенные');
        expect(PROFILE_METRIC_LABELS.inWork).toBe('В работе');
        expect(PROFILE_METRIC_LABELS.interviews).not.toMatch(/рейс/i);
        expect(PROFILE_METRIC_LABELS.hired).not.toMatch(/выручк/i);
    });

    it('formats this-week interview delta', () => {
        expect(interviewsWeekHint(5)).toBe('+5 за эту неделю');
        expect(interviewsWeekHint(0)).toBe('0 за эту неделю');
        expect(interviewsWeekHint(null)).toBe('0 за эту неделю');
    });
});
