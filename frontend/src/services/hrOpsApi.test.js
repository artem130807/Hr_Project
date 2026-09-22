jest.mock('../config/api', () => ({
    API_URL: 'http://api.test',
    API_PREFIX: '/v1',
}));

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
        patch: jest.fn(),
        put: jest.fn(),
        del: jest.fn(),
    },
}));

describe('hrOpsApi + hiringRequestsApi workflows', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.post.mockReset();
        http.patch.mockReset();
        http.put.mockReset();
        http.del.mockReset();
    });

    it('createVacancyFromHiringRequest posts create-vacancy', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ id: 42, name: 'Логист' });
        const { createVacancyFromHiringRequest } = require('./hiringRequestsApi');
        const result = await createVacancyFromHiringRequest(7);
        expect(http.post).toHaveBeenCalledWith('/hiring-requests/7/create-vacancy', {});
        expect(result.id).toBe(42);
    });

    it('publishHiringRequestToHH posts publish-hh', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ status: 'ok', hh_vacancy_id: '99' });
        const { publishHiringRequestToHH } = require('./hiringRequestsApi');
        const result = await publishHiringRequestToHH(7);
        expect(http.post).toHaveBeenCalledWith('/hiring-requests/7/publish-hh', {});
        expect(result.hh_vacancy_id).toBe('99');
    });

    it('updateHiringRequest patches body', async () => {
        const { http } = require('../utils/http');
        http.patch.mockResolvedValue({ id: 1, position: 'X' });
        const { updateHiringRequest } = require('./hiringRequestsApi');
        await updateHiringRequest(1, { position: 'X' });
        expect(http.patch).toHaveBeenCalledWith('/hiring-requests/1', { position: 'X' });
    });

    it('createApproval posts approval payload', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ id: 1 });
        const { createApproval } = require('./hrOpsApi');
        await createApproval({
            vacancy_id: 2,
            candidate_id: 3,
            approver_id: "4",
            new_status: 'Одобрен рекрутером',
            comments: 'ok',
        });
        expect(http.post).toHaveBeenCalledWith('/approvals', expect.objectContaining({
            vacancy_id: 2,
            candidate_id: 3,
        }));
    });

    it('getCandidateStageHistory and comments use candidate routes', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([]);
        http.post.mockResolvedValue({ id: 9, body: 'hi' });
        const {
            getCandidateStageHistory,
            getCandidateComments,
            createCandidateComment,
            getAuditLogs,
        } = require('./hrOpsApi');

        await getCandidateStageHistory(5);
        await getCandidateComments(5);
        await createCandidateComment(5, { body: 'hi', author_name: 'HR' });
        await getAuditLogs({ entityType: 'candidate', entityId: 5, limit: 50 });

        expect(http.get).toHaveBeenCalledWith('/candidate/5/stage-history');
        expect(http.get).toHaveBeenCalledWith('/candidate/5/comments');
        expect(http.post).toHaveBeenCalledWith('/candidate/5/comments', {
            body: 'hi',
            author_name: 'HR',
        });
        expect(http.get).toHaveBeenCalledWith(
            expect.stringContaining('/audit-logs?')
        );
    });

    it('deleteCandidateComment uses nested candidate path', async () => {
        const { http } = require('../utils/http');
        http.del.mockResolvedValue(null);
        const { deleteCandidateComment } = require('./hrOpsApi');
        await deleteCandidateComment(5, 9);
        expect(http.del).toHaveBeenCalledWith('/candidate/5/comments/9');
    });

    it('hired employees list endpoint', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([{ id: 1, full_name: 'A' }]);
        const { getHiredEmployees } = require('./hrOpsApi');
        const list = await getHiredEmployees('IT');
        expect(http.get).toHaveBeenCalledWith('/employees?department=IT');
        expect(list).toHaveLength(1);
    });

    it('getVnrHires queries vnr-hires with filters', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([]);
        const { getVnrHires } = require('./hrOpsApi');
        await getVnrHires({ hrUserId: 'hr-1', activeOnly: false, mine: true });
        expect(http.get).toHaveBeenCalledWith(
            expect.stringContaining('/vnr-hires?')
        );
        const url = http.get.mock.calls[0][0];
        expect(url).toContain('hr_user_id=hr-1');
        expect(url).toContain('active_only=false');
        expect(url).toContain('mine=true');
    });

    it('createEmployee posts to /employees', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ id: 5, full_name: 'Иванов' });
        const { createEmployee } = require('./hrOpsApi');
        const body = { full_name: 'Иванов', department: 'hr', position: 'HR' };
        const row = await createEmployee(body);
        expect(http.post).toHaveBeenCalledWith('/employees', body);
        expect(row.id).toBe(5);
    });

    it('changes hiring request status with structured reason', async () => {
        const { http } = require('../utils/http');
        http.put.mockResolvedValue({ id: 1, status: 'возвращена на уточнение' });
        const { updateHiringRequestStatus } = require('./hiringRequestsApi');
        await updateHiringRequestStatus(1, 'возвращена на уточнение', { comment: 'Уточните график' });
        expect(http.put).toHaveBeenCalledWith('/hiring-requests/1/status', {
            status: 'возвращена на уточнение',
            comment: 'Уточните график',
        });
    });

    it('loads append-only hiring request history', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([]);
        const { getHiringRequestHistory } = require('./hiringRequestsApi');
        await getHiringRequestHistory(12);
        expect(http.get).toHaveBeenCalledWith('/hiring-requests/12/history');
    });

    it('uses unauthenticated public invitation endpoints', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ expires_at: '2026-09-20T00:00:00Z' });
        http.post.mockResolvedValue({ id: 9, public_code: 'З-9' });
        const {
            createHiringRequestInvite,
            getPublicHiringRequestInvite,
            submitPublicHiringRequest,
        } = require('./hiringRequestsApi');

        await createHiringRequestInvite();
        await getPublicHiringRequestInvite('a/b');
        await submitPublicHiringRequest('a/b', { position: 'Логист' });

        expect(http.post).toHaveBeenCalledWith('/hiring-request-invites', {});
        expect(http.get).toHaveBeenCalledWith('/public/hiring-request-invites/a%2Fb', { auth: false });
        expect(http.post).toHaveBeenCalledWith(
            '/public/hiring-request-invites/a%2Fb',
            { position: 'Логист' },
            { auth: false },
        );
    });

    it('uses contact directory and organization routes', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([]);
        http.post.mockResolvedValue({ id: 8 });
        http.patch.mockResolvedValue({ id: 8 });
        http.del.mockResolvedValue(null);
        const api = require('./hrOpsApi');
        await api.getEmployeeContacts(4);
        await api.createEmployeeContact(4, { contact_type: 'telegram' });
        await api.updateContact(8, { is_primary: true });
        await api.deactivateContact(8);
        await api.getOrganizationDepartments();
        await api.getOrganizationDepartment(2);
        await api.createDepartmentContact(2, { contact_type: 'email' });
        expect(http.get).toHaveBeenCalledWith('/employees/4/contacts');
        expect(http.post).toHaveBeenCalledWith('/employees/4/contacts', { contact_type: 'telegram' });
        expect(http.patch).toHaveBeenCalledWith('/contacts/8', { is_primary: true });
        expect(http.del).toHaveBeenCalledWith('/contacts/8');
        expect(http.get).toHaveBeenCalledWith('/organization/departments');
        expect(http.get).toHaveBeenCalledWith('/organization/departments/2');
        expect(http.post).toHaveBeenCalledWith('/organization/departments/2/contacts', { contact_type: 'email' });
    });
});
