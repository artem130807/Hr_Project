/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import EmployeePage from './EmployeePage';

jest.mock(
    'react-router-dom',
    () => ({
        NavLink: ({ children, to }) => <a href={to}>{children}</a>,
        useNavigate: () => jest.fn(),
    }),
    { virtual: true }
);

const mockShowAlert = jest.fn();

jest.mock('../context/AlertContext', () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));

jest.mock('../context/AuthContext', () => ({
    useAuth: () => ({
        user: { id: 1, role: 'hr', username: 'hr' },
        logout: jest.fn(),
    }),
}));

jest.mock('../services/userApi', () => ({
    getUsers: jest.fn(),
    getInviteUrl: jest.fn(),
    getAdminRoles: jest.fn(() => Promise.resolve([{ id: 1, name: 'HR', role: 'hr' }])),
    createUser: jest.fn(),
}));
jest.mock('../services/hhAuthApi', () => ({
    checkHHAuth: jest.fn(() => Promise.resolve({ auth_passed: true })),
    getHHAuthLink: jest.fn(() => Promise.resolve('https://hh.example/auth')),
}));
jest.mock('../components/sidebar/AutoSelectSection', () => () => null);
jest.mock('../components/notifications/NotificationBell', () => () => null);
jest.mock('../utils/excelUtils', () => ({ exportEmployeesToExcel: jest.fn() }));

jest.mock('../services/hrOpsApi', () => ({
    getHiredEmployees: jest.fn(),
    getVnrHires: jest.fn(),
    createEmployee: jest.fn(),
    deleteEmployee: jest.fn(),
}));

const { getHiredEmployees, getVnrHires, createEmployee } = require('../services/hrOpsApi');
const { getUsers, createUser } = require('../services/userApi');

describe('EmployeePage', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        getHiredEmployees.mockReset();
        getVnrHires.mockReset();
        createEmployee.mockReset();
        getUsers.mockReset();
        createUser.mockReset();
        getHiredEmployees.mockResolvedValue([]);
        getVnrHires.mockResolvedValue([]);
        getUsers.mockResolvedValue([]);
        createEmployee.mockResolvedValue({
            id: 9,
            full_name: 'Новый Сотрудник',
            department: 'hr',
            position: 'Специалист',
            date_hired: '2026-08-17',
        });
        createUser.mockResolvedValue({
            id: 'u-1',
            username: 'new@ex.com',
            full_name: 'Панель Юзер',
            role: 'hr',
        });
    });

    it('defaults to the unified directory and opens ERP create form', async () => {
        render(<EmployeePage />);
        expect(await screen.findByTestId('all-employees-table')).toBeInTheDocument();
        expect(await screen.findByTestId('add-panel-user')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('add-panel-user'));
        expect(await screen.findByTestId('panel-user-form')).toBeInTheDocument();
    });

    it('creates an ERP user with a work start date', async () => {
        render(<EmployeePage />);
        fireEvent.click(await screen.findByTestId('add-panel-user'));
        fireEvent.change(await screen.findByTestId('panel-user-name'), {
            target: { value: 'Пользователь ERP' },
        });
        fireEvent.change(screen.getByTestId('panel-user-email'), {
            target: { value: 'erp-user@example.ru' },
        });
        fireEvent.change(screen.getByTestId('panel-user-date-hired'), {
            target: { value: '2026-09-21' },
        });
        fireEvent.click(screen.getByTestId('panel-user-submit'));

        await waitFor(() => expect(createUser).toHaveBeenCalledWith(expect.objectContaining({
            date_hired: '2026-09-21',
        })));
        await waitFor(() => expect(getHiredEmployees.mock.calls.length).toBeGreaterThanOrEqual(2));
    });

    it('shows ERP and local HR employees in one table', async () => {
        getUsers.mockResolvedValue([
            { id: 'erp-1', full_name: 'Сотрудник ERP', username: 'erp@example.ru', department: 'Продажи', role: 'leader' },
        ]);
        getHiredEmployees.mockResolvedValue([
            { id: 18, full_name: 'Сотрудник HR', department: 'Склад', position: 'Кладовщик', date_hired: '2026-09-01' },
        ]);

        render(<EmployeePage />);

        const table = await screen.findByTestId('all-employees-table');
        await waitFor(() => expect(table).toHaveTextContent('Сотрудник ERP'));
        expect(table).toHaveTextContent('Сотрудник HR');
        expect(table).toHaveTextContent('ERP');
        expect(table).toHaveTextContent('HR-платформа');
        expect(screen.getByTestId('add-hired-employee')).toHaveTextContent('Добавить сотрудника');
    });

    it('merges linked ERP and HR records into one employee row', async () => {
        getUsers.mockResolvedValue([
            { id: 'erp-7', full_name: 'Связанный сотрудник', username: 'linked@example.ru', department: 'IT' },
        ]);
        getHiredEmployees.mockResolvedValue([
            { id: 21, erp_user_id: 'erp-7', full_name: 'Связанный сотрудник', department: 'IT', position: 'Разработчик', date_hired: '2026-09-02' },
        ]);

        render(<EmployeePage />);

        const table = await screen.findByTestId('all-employees-table');
        await waitFor(() => expect(table).toHaveTextContent('Связанный сотрудник'));
        expect(screen.getAllByText('Связанный сотрудник')).toHaveLength(1);
        expect(table).toHaveTextContent('ERP');
        expect(table).toHaveTextContent('HR-платформа');
    });

    it('opens hired create form and adds employee to list', async () => {
        render(<EmployeePage />);
        fireEvent.click(await screen.findByTestId('tab-hired'));
        await waitFor(() => expect(getVnrHires).toHaveBeenCalled());
        expect(await screen.findByTestId('add-hired-employee')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('add-hired-employee'));
        expect(await screen.findByTestId('hired-employee-form')).toBeInTheDocument();

        fireEvent.change(screen.getByTestId('employee-full-name'), {
            target: { value: 'Новый Сотрудник' },
        });
        fireEvent.change(screen.getByTestId('employee-position'), {
            target: { value: 'Специалист' },
        });
        fireEvent.click(screen.getByTestId('employee-submit'));

        await waitFor(() => expect(createEmployee).toHaveBeenCalled());
        expect(await screen.findByText('Новый Сотрудник')).toBeInTheDocument();
    });

    it('lists VNR hires with HR name on hired tab', async () => {
        getVnrHires.mockResolvedValue([
            {
                id: 1,
                hr_user_id: 'hr-1',
                hr_user_name: 'Анна HR',
                candidate_id: 7,
                employee_id: 11,
                full_name: 'Петров Пётр',
                department: 'it',
                position: 'Backend',
                hired_at: '2026-08-27T10:00:00Z',
                status: 'in_work',
            },
        ]);
        render(<EmployeePage />);
        fireEvent.click(await screen.findByTestId('tab-hired'));
        expect(await screen.findByText('Петров Пётр')).toBeInTheDocument();
        expect(screen.getByText('Анна HR')).toBeInTheDocument();
        expect(screen.getByText('#7')).toBeInTheDocument();
    });
});
