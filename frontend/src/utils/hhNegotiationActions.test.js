/**
 * @jest-environment node
 */
import {
    hhActionLabel,
    actionNeedsMessage,
    enabledActions,
    actionButtonVariant,
} from './hhNegotiationActions';

describe('hhNegotiationActions', () => {
    it('prefers HH name when distinct from id', () => {
        expect(hhActionLabel({ id: 'discard', name: 'Отказать кандидату' })).toBe(
            'Отказать кандидату'
        );
    });

    it('falls back to Russian label map', () => {
        expect(hhActionLabel({ id: 'interview', name: 'interview' })).toBe(
            'Пригласить на собеседование'
        );
    });

    it('detects message argument', () => {
        expect(
            actionNeedsMessage({
                id: 'discard',
                arguments: [{ id: 'message', required: false }],
            })
        ).toBe(true);
        expect(actionNeedsMessage({ id: 'hired', arguments: [] })).toBe(false);
    });

    it('filters enabled actions only', () => {
        expect(
            enabledActions([
                { id: 'discard', enabled: true },
                { id: 'interview', enabled: false },
                { id: null, enabled: true },
            ]).map((a) => a.id)
        ).toEqual(['discard']);
    });

    it('maps button variants', () => {
        expect(actionButtonVariant('discard')).toBe('danger');
        expect(actionButtonVariant('hired')).toBe('success');
        expect(actionButtonVariant('interview')).toBe('primary');
    });
});
