import { buildCandidateFunnelRows, totalFunnelCount } from './candidateAnalytics';

describe('candidateAnalytics', () => {
    it('builds ordered funnel rows with zeros for missing statuses', () => {
        const rows = buildCandidateFunnelRows({
            'откликнулся': 3,
            'ВНР': 1,
        });
        expect(rows[0].name).toBe('холодный контакт');
        expect(rows[0].count).toBe(0);
        expect(rows.find((r) => r.name === 'откликнулся').count).toBe(3);
        expect(rows.find((r) => r.name === 'ВНР').count).toBe(1);
        expect(rows.find((r) => r.name === 'уволился').depth).toBe(5);
        expect(totalFunnelCount(rows)).toBe(4);
    });
});
