/**
 * @jest-environment node
 */
jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
        patch: jest.fn(),
        del: jest.fn(),
    },
}));

const { http } = require('../utils/http');
const { createUser, getAdminRoles } = require('./userApi');

describe('userApi ERP create', () => {
    beforeEach(() => {
        http.get.mockReset();
        http.post.mockReset();
        http.patch.mockReset();
    });

    it('unwraps { user, password } from POST /admin/user', async () => {
        http.post.mockResolvedValue({
            user: {
                id: 'u-1',
                username: 'a@ex.com',
                full_name: 'Ann',
                role: 'hr',
            },
            password: 'Generated1#',
        });

        const result = await createUser({
            username: 'a@ex.com',
            full_name: 'Ann',
            role: 'hr',
            password: null,
            date_hired: '2026-09-21',
        });

        expect(http.post).toHaveBeenCalledWith('/admin/user', expect.objectContaining({
            username: 'a@ex.com',
            role: 'hr',
            plain_password: null,
            date_hired: '2026-09-21',
        }));
        expect(result.id).toBe('u-1');
        expect(result.generated_password).toBe('Generated1#');
    });

    it('getAdminRoles hits /admin/roles', async () => {
        http.get.mockResolvedValue([{ id: 1, name: 'HR', role: 'hr' }]);
        const roles = await getAdminRoles();
        expect(http.get).toHaveBeenCalledWith('/admin/roles');
        expect(roles[0].role).toBe('hr');
    });

    it('updateUser patches /admin/user/:id', async () => {
        http.patch.mockResolvedValue({
            id: 'u-1',
            username: 'a@ex.com',
            full_name: 'Ann Updated',
            role: 'manager',
        });
        const { updateUser } = require('./userApi');
        const result = await updateUser('u-1', {
            username: 'a@ex.com',
            full_name: 'Ann Updated',
            role: 'manager',
            date_hired: '2026-09-21',
        });
        expect(http.patch).toHaveBeenCalledWith(
            '/admin/user/u-1',
            expect.objectContaining({
                username: 'a@ex.com',
                full_name: 'Ann Updated',
                role: 'manager',
                date_hired: '2026-09-21',
            })
        );
        expect(result.full_name).toBe('Ann Updated');
    });
});
