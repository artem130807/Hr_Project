/**
 * @jest-environment jsdom
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useCandidatesList } from './useCandidatesList';
import { getCandidates } from '../services/candidateApi';

jest.mock('../services/candidateApi', () => ({
    getCandidates: jest.fn(),
}));

jest.mock('../utils/candidateMapper', () => ({
    mapCandidateFromBackend: (c) => c,
}));

describe('useCandidatesList', () => {
    beforeEach(() => {
        getCandidates.mockReset();
        getCandidates.mockResolvedValue({
            items: [{ id: 1, full_name: 'A' }],
            total: 1,
            page: 1,
            per_page: 20,
            total_pages: 1,
        });
    });

    it('loads first page for default filters', async () => {
        const onError = jest.fn();
        const { result } = renderHook(() =>
            useCandidatesList({
                statusFilter: null,
                debouncedSearch: '',
                roleFilter: '',
                vacancyIds: [],
                onlyPerfect: false,
                categoryFilter: 'candidate',
                onError,
            })
        );

        await waitFor(() => expect(getCandidates).toHaveBeenCalled(), { timeout: 3000 });
        await waitFor(() => expect(result.current.listLoading).toBe(false));
        expect(result.current.candidates).toHaveLength(1);
        expect(result.current.total).toBe(1);
        expect(onError).not.toHaveBeenCalled();
    });

    it('ignores abort errors without calling onError', async () => {
        const onError = jest.fn();
        const abortErr = new Error('Aborted');
        abortErr.name = 'AbortError';
        getCandidates.mockRejectedValueOnce(abortErr);

        const { result } = renderHook(() =>
            useCandidatesList({
                statusFilter: null,
                debouncedSearch: '',
                roleFilter: '',
                vacancyIds: [],
                onlyPerfect: false,
                categoryFilter: 'candidate',
                onError,
            })
        );

        await waitFor(() => expect(getCandidates).toHaveBeenCalled(), { timeout: 3000 });
        await waitFor(() => expect(result.current.listLoading).toBe(false));
        expect(onError).not.toHaveBeenCalled();
        expect(result.current.candidates).toEqual([]);
    });

    it('passes multi vacancy ids to API', async () => {
        const { rerender } = renderHook(
            ({ vacancyIds }) =>
                useCandidatesList({
                    statusFilter: null,
                    debouncedSearch: '',
                    roleFilter: '',
                    vacancyIds,
                    onlyPerfect: false,
                    categoryFilter: 'candidate',
                    onError: jest.fn(),
                }),
            { initialProps: { vacancyIds: [] } }
        );

        await waitFor(() => expect(getCandidates).toHaveBeenCalled(), { timeout: 3000 });
        getCandidates.mockClear();

        await act(async () => {
            rerender({ vacancyIds: [3, 1] });
        });

        await waitFor(() => expect(getCandidates).toHaveBeenCalled(), { timeout: 3000 });
        const args = getCandidates.mock.calls[0];
        expect(args[3]).toEqual([1, 3]); // sorted by key
    });
});
