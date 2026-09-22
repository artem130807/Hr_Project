import {
    normalizeCandidatesPage,
    mergeCandidatesById,
    CANDIDATES_PAGE_SIZE,
} from './candidatesPagination';

describe('candidatesPagination', () => {
    it('normalizes PaginatedResponse and computes hasMore', () => {
        const page = normalizeCandidatesPage(
            {
                items: [{ id: 1 }, { id: 2 }],
                total: 40,
                page: 1,
                per_page: 20,
                total_pages: 2,
            },
            { page: 0, perPage: 20 }
        );
        expect(page.items).toHaveLength(2);
        expect(page.hasMore).toBe(true);
        expect(page.total_pages).toBe(2);
    });

    it('hasMore is false on last page', () => {
        const page = normalizeCandidatesPage(
            {
                items: [{ id: 21 }],
                total: 21,
                page: 2,
                per_page: 20,
                total_pages: 2,
            },
            { page: 1, perPage: 20 }
        );
        expect(page.hasMore).toBe(false);
    });

    it('accepts bare array as a single page', () => {
        const page = normalizeCandidatesPage([{ id: 1 }], { page: 0 });
        expect(page.items).toEqual([{ id: 1 }]);
        expect(page.hasMore).toBe(false);
        expect(page.total_pages).toBe(1);
    });

    it('mergeCandidatesById appends without duplicates', () => {
        const merged = mergeCandidatesById(
            [{ id: 1, full_name: 'A' }],
            [{ id: 1, full_name: 'A2' }, { id: 2, full_name: 'B' }]
        );
        expect(merged).toHaveLength(2);
        expect(merged[0].full_name).toBe('A');
        expect(merged[1].id).toBe(2);
    });

    it('exports default page size', () => {
        expect(CANDIDATES_PAGE_SIZE).toBe(20);
    });
});
