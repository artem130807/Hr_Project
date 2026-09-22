/**
 * @jest-environment node
 */
import { menuItemsForRole, rolesForPath, psychPublicTakePath, professionalPublicTakePath, isNavGroup, defaultPathForRole, isLeaderRole } from './navConfig';


describe('navConfig tests submenu', () => {
    it('exposes Тесты as a group with Создание and Результаты', () => {
        const items = menuItemsForRole('hr');
        const tests = items.find((i) => i.label === 'Тесты');
        expect(isNavGroup(tests)).toBe(true);
        expect(tests.children.map((c) => c.to)).toEqual(['/tests', '/tests/results', '/tests/adaptation']);
        expect(tests.children.map((c) => c.label)).toEqual([
            'Создание тестов',
            'Результаты тестов',
            'Адаптация',
        ]);
    });

    it('rolesForPath covers both test routes', () => {
        expect(rolesForPath('/tests')).toEqual(expect.arrayContaining(['hr', 'owner', 'dev']));
        expect(rolesForPath('/tests/results')).toEqual(
            expect.arrayContaining(['hr', 'owner', 'dev'])
        );
        expect(rolesForPath('/tests/adaptation')).toEqual(
            expect.arrayContaining(['hr', 'owner', 'dev'])
        );
        expect(rolesForPath('/tests/adaptation/7')).toEqual(
            expect.arrayContaining(['hr', 'owner', 'dev'])
        );
    });

    it('builds public take path', () => {
        expect(psychPublicTakePath('complex_work_behavior_220')).toBe(
            '/take/complex_work_behavior_220'
        );
        expect(professionalPublicTakePath(42)).toBe('/take/test/42');
    });

    it('still hides /logs', () => {
        expect(menuItemsForRole('owner').map((i) => (i.to ? i.to : i.label))).not.toContain(
            '/logs'
        );
    });

    it('labels analytics as Статистика кандидатов', () => {
        const items = menuItemsForRole('hr');
        const analytics = items.find((i) => i.to === '/analytics');
        expect(analytics?.label).toBe('Статистика кандидатов');
    });

    it('allows ERP roles to open /profile', () => {
        const roles = rolesForPath('/profile');
        expect(roles).toEqual(
            expect.arrayContaining(['hr', 'owner', 'manager', 'admin', 'leader', 'dept_leader'])
        );
        expect(menuItemsForRole('manager').some((i) => i.to === '/profile')).toBe(false);
    });

    it('lets HR open department profiles without a department on the user card', () => {
        expect(rolesForPath('/departments')).toEqual(expect.arrayContaining(['hr', 'owner', 'lead', 'dev']));
        expect(menuItemsForRole('hr').some((i) => i.to === '/departments')).toBe(true);
    });

    it('limits ERP руководитель to requests, employees, portrait, departments', () => {
        const allowed = ['/requests', '/employees', '/candidate-portrait', '/departments', '/organization'];
        for (const role of ['leader', 'dept_leader']) {
            expect(isLeaderRole(role)).toBe(true);
            const paths = menuItemsForRole(role).map((i) => i.to);
            expect(paths).toEqual(allowed);
            expect(defaultPathForRole(role)).toBe('/requests');
            expect(rolesForPath('/profile')).toEqual(expect.arrayContaining([role]));
            expect(rolesForPath('/dashboard')).not.toContain(role);
            expect(rolesForPath('/candidates')).not.toContain(role);
            expect(rolesForPath('/vacancies')).not.toContain(role);
            expect(rolesForPath('/tests')).not.toContain(role);
        }
        expect(menuItemsForRole('leader').some((i) => i.to === '/profile')).toBe(false);
    });

    it('does not strip HR workspace from ERP manager', () => {
        expect(menuItemsForRole('manager').map((i) => i.to)).toEqual(
            expect.arrayContaining(['/dashboard', '/candidates', '/vacancies'])
        );
        expect(defaultPathForRole('hr')).toBe('/dashboard');
    });

    it('exposes Звонки with a phone icon for HR', () => {
        const items = menuItemsForRole('hr');
        const calls = items.find((i) => i.to === '/calls');
        expect(calls?.label).toBe('Звонки');
        expect(calls?.icon).toBe('PhoneIcon');
        expect(rolesForPath('/calls')).toEqual(expect.arrayContaining(['hr', 'owner', 'dev']));
    });

    it('allows all signed-in panel roles to open notifications without adding a sidebar item', () => {
        expect(rolesForPath('/notifications')).toEqual(
            expect.arrayContaining(['hr', 'owner', 'manager', 'leader', 'dept_leader'])
        );
        expect(menuItemsForRole('hr').some((item) => item.to === '/notifications')).toBe(false);
    });
});
