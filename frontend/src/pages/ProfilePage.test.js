/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import ProfilePage from './ProfilePage';

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
        user: { id: 'hr-1', erp_user_id: 'hr-1', role: 'hr', username: 'anna', name: 'Анна' },
        logout: jest.fn(),
    }),
}));

jest.mock('../services/hhAuthApi', () => ({
    checkHHAuth: jest.fn(() => Promise.resolve({ auth_passed: true })),
    getHHAuthLink: jest.fn(() => Promise.resolve('https://hh.example/auth')),
}));
jest.mock('../components/sidebar/AutoSelectSection', () => () => null);
jest.mock('../components/notifications/NotificationBell', () => () => null);

jest.mock('../services/analyticsApi', () => ({
    getHrProfileStats: jest.fn(),
}));

const { getHrProfileStats } = require('../services/analyticsApi');

describe('ProfilePage VNR stats', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        getHrProfileStats.mockReset();
        getHrProfileStats.mockResolvedValue({
            hr_user_id: 'hr-1',
            hired: 6,
            in_work: 5,
            interviews: 26,
            interviews_this_week: 5,
        });
    });

    it('renders hired and in-work counts from API', async () => {
        render(<ProfilePage />);
        await waitFor(() => expect(getHrProfileStats).toHaveBeenCalled());
        expect(await screen.findByTestId('profile-hired-count')).toHaveTextContent('6');
        expect(screen.getByTestId('profile-in-work-count')).toHaveTextContent('В работе: 5');
    });

    it('renders interview counts from HR calendar bookings', async () => {
        render(<ProfilePage />);
        expect(await screen.findByTestId('profile-interviews-count')).toHaveTextContent('26');
        expect(screen.getByTestId('profile-interviews-week')).toHaveTextContent('+5 за эту неделю');
    });
});
