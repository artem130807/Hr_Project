/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import DepartmentProfilesPage from './DepartamentProfilesPage';

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

jest.mock('../layout/MainLayout', () => ({ children }) => <div>{children}</div>);

jest.mock('../services/candidateImageApi', () => ({
    listDepartmentCandidateImages: jest.fn(),
    createDepartmentCandidateImage: jest.fn(),
    updateDepartmentCandidateImage: jest.fn(),
}));

const {
    listDepartmentCandidateImages,
    createDepartmentCandidateImage,
} = require('../services/candidateImageApi');

describe('DepartmentProfilesPage', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        listDepartmentCandidateImages.mockReset();
        createDepartmentCandidateImage.mockReset();
        listDepartmentCandidateImages.mockResolvedValue([]);
        createDepartmentCandidateImage.mockResolvedValue({ id: 1, department: 'hr' });
    });

    it('loads all department profiles for HR without a department on the user card', async () => {
        render(<DepartmentProfilesPage />);
        expect(await screen.findByText(/профили отделов пока не созданы/i)).toBeInTheDocument();
        expect(listDepartmentCandidateImages).toHaveBeenCalled();
        expect(mockShowAlert).not.toHaveBeenCalledWith(
            expect.stringMatching(/не указан отдел/i),
            expect.anything()
        );
        expect(screen.getByTestId('department-profile-create')).toBeInTheDocument();
    });

    it('creates a profile for a department chosen from the list', async () => {
        render(<DepartmentProfilesPage />);
        fireEvent.click(await screen.findByTestId('department-profile-create'));
        fireEvent.change(screen.getByTestId('department-profile-department'), {
            target: { value: 'логистический' },
        });
        fireEvent.click(screen.getByRole('button', { name: /создать профиль/i }));
        await waitFor(() =>
            expect(createDepartmentCandidateImage).toHaveBeenCalledWith(
                expect.objectContaining({
                    department: 'логистический',
                    lead_id: '1',
                })
            )
        );
    });
});
