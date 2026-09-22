import { canCreateHiringRequest, canGenerateHiringRequestInvite } from './hiringRequestsApi';

describe('hiringRequestsApi helpers', () => {
    it('allows legacy and ERP roles to create hiring requests', () => {
        expect(canCreateHiringRequest('lead')).toBe(true);
        expect(canCreateHiringRequest('owner')).toBe(true);
        expect(canCreateHiringRequest('hr')).toBe(true);
        expect(canCreateHiringRequest('leader')).toBe(true);
        expect(canCreateHiringRequest('dept_leader')).toBe(true);
        expect(canCreateHiringRequest('manager')).toBe(true);
        expect(canCreateHiringRequest('art')).toBe(false);
        expect(canCreateHiringRequest(null)).toBe(false);
    });

    it('allows HR roles, but not department leaders, to generate public links', () => {
        expect(canGenerateHiringRequestInvite('hr')).toBe(true);
        expect(canGenerateHiringRequestInvite('admin')).toBe(true);
        expect(canGenerateHiringRequestInvite('manager')).toBe(true);
        expect(canGenerateHiringRequestInvite('leader')).toBe(false);
        expect(canGenerateHiringRequestInvite('dept_leader')).toBe(false);
    });
});
