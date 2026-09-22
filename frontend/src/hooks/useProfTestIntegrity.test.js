/**
 * @jest-environment jsdom
 */
import { act, renderHook } from '@testing-library/react';
import { useProfTestIntegrity } from './useProfTestIntegrity';

describe('useProfTestIntegrity', () => {
    it('coalesces visibilitychange + window blur into one tab violation', () => {
        const onTabBlur = jest.fn(() => true);
        const { result } = renderHook(() =>
            useProfTestIntegrity({ enabled: true, onTabBlur, onMouseLeave: jest.fn() })
        );

        act(() => {
            Object.defineProperty(document, 'visibilityState', {
                configurable: true,
                get: () => 'hidden',
            });
            document.dispatchEvent(new Event('visibilitychange'));
            window.dispatchEvent(new Event('blur'));
        });

        expect(onTabBlur).toHaveBeenCalledTimes(1);
        expect(result.current.tabBlurCount).toBe(1);
    });

    it('skips counter when callback returns false', () => {
        const onMouseLeave = jest.fn(() => false);
        const { result } = renderHook(() =>
            useProfTestIntegrity({ enabled: true, onTabBlur: jest.fn(), onMouseLeave })
        );

        act(() => {
            result.current.handleZoneMouseLeave();
        });

        expect(onMouseLeave).toHaveBeenCalled();
        expect(result.current.mouseLeaveCount).toBe(0);
    });
});
