/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import AnalyticsPage from './AnalyticsPage';

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

jest.mock('../services/userApi', () => ({ getInviteUrl: jest.fn() }));
jest.mock('../services/hhAuthApi', () => ({
    checkHHAuth: jest.fn(() => Promise.resolve({ auth_passed: true })),
    getHHAuthLink: jest.fn(() => Promise.resolve('https://hh.example/auth')),
}));
jest.mock('../components/sidebar/AutoSelectSection', () => () => null);
jest.mock('../components/notifications/NotificationBell', () => () => null);

jest.mock('../components/analytics/FunnelChart', () => () => (
    <div data-testid="funnel-chart-mock" />
));

jest.mock('../services/analyticsApi', () => ({
    getActiveCandidates: jest.fn(),
    exportAnalyticsTable: jest.fn(),
}));
jest.mock('../services/vacancyApi', () => ({
    getVacancyOptions: jest.fn(),
}));

const { getActiveCandidates, exportAnalyticsTable } = require('../services/analyticsApi');
const { getVacancyOptions } = require('../services/vacancyApi');

describe('AnalyticsPage', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        getActiveCandidates.mockReset();
        exportAnalyticsTable.mockReset();
        getActiveCandidates.mockResolvedValue({
            stats: {
                'откликнулся': 2,
                'собес': 1,
                'ВНР': 1,
            },
        });
        getVacancyOptions.mockResolvedValue([
            { id: 10, name: 'Логист' },
            { id: 11, name: 'Водитель' },
        ]);
        exportAnalyticsTable.mockResolvedValue(undefined);
    });

    it('renders candidate statistics title and funnel statuses', async () => {
        render(<AnalyticsPage />);
        expect(await screen.findByTestId('analytics-page-title')).toHaveTextContent(
            'Статистика кандидатов'
        );
        expect(await screen.findByTestId('analytics-total')).toHaveTextContent('4');
        expect(screen.getByTestId('analytics-status-cards')).toHaveTextContent('откликнулся');
        expect(screen.getByTestId('analytics-status-cards')).toHaveTextContent('тест: отправлен');
        expect(screen.getByTestId('analytics-table')).toHaveTextContent('уволился');
        expect(screen.getByTestId('funnel-chart-mock')).toBeInTheDocument();
        expect(screen.getByTestId('analytics-vacancy-select')).toBeInTheDocument();
    });

    it('exports excel for selected period', async () => {
        render(<AnalyticsPage />);
        await screen.findByTestId('analytics-page-title');
        fireEvent.click(screen.getByTestId('analytics-export'));
        await waitFor(() => expect(exportAnalyticsTable).toHaveBeenCalled());
        const [from, to] = exportAnalyticsTable.mock.calls[0];
        expect(from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('requests analytics for selected vacancy', async () => {
        render(<AnalyticsPage />);
        await screen.findByTestId('analytics-page-title');

        fireEvent.change(screen.getByTestId('analytics-vacancy-select'), {
            target: { value: '10' },
        });
        await waitFor(() => {
            expect(getActiveCandidates).toHaveBeenLastCalledWith('10');
        });
    });
});
