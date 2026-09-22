/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import VacancyFilterStepModal from './VacancyFilterStepModal';

jest.mock('../../services/vacancyFilterApi', () => ({
    listVacancyFilters: jest.fn(),
    createVacancyFilter: jest.fn(),
    updateVacancyFilter: jest.fn(),
    assignFilterToVacancy: jest.fn(),
    unassignFilterFromVacancy: jest.fn(),
}));

jest.mock('../../context/AlertContext', () => ({
    useAlertContext: () => ({ showAlert: jest.fn() }),
}));

const {
    listVacancyFilters,
    createVacancyFilter,
    updateVacancyFilter,
    assignFilterToVacancy,
    unassignFilterFromVacancy,
} = require('../../services/vacancyFilterApi');

describe('VacancyFilterStepModal', () => {
    const vacancy = { id: 42, name: 'Логист' };
    const existing = [
        {
            id: 1,
            city: 'Москва',
            age_from: 25,
            age_to: 40,
            experience: 'between1And3',
            work_format: 'remote',
        },
        {
            id: 2,
            city: 'Казань',
            age_from: null,
            age_to: null,
            experience: null,
            work_format: 'office',
        },
    ];

    beforeEach(() => {
        listVacancyFilters.mockReset();
        createVacancyFilter.mockReset();
        updateVacancyFilter.mockReset();
        assignFilterToVacancy.mockReset();
        unassignFilterFromVacancy.mockReset();
        listVacancyFilters.mockResolvedValue(existing);
        assignFilterToVacancy.mockResolvedValue({ id: 42, filter_id: 1 });
        updateVacancyFilter.mockResolvedValue({ id: 1, city: 'СПб', work_format: 'remote' });
        unassignFilterFromVacancy.mockResolvedValue({ id: 42, filter_id: null });
        createVacancyFilter.mockResolvedValue({
            id: 9,
            city: 'Новосибирск',
            work_format: 'hybrid',
        });
    });

    it('loads existing filters and shows details on select', async () => {
        render(
            <VacancyFilterStepModal
                vacancy={vacancy}
                onDone={jest.fn()}
                onSkip={jest.fn()}
            />
        );

        expect(await screen.findByText(/фильтр для вакансии/i)).toBeInTheDocument();
        const moscowBtn = await screen.findByRole('button', { name: /фильтр: москва/i });
        fireEvent.click(moscowBtn);

        const details = await screen.findByTestId('filter-details');
        expect(within(details).getByText(/удал/i)).toBeInTheDocument();
        expect(within(details).getByText(/25/)).toBeInTheDocument();
    });

    it('assigns selected filter to vacancy', async () => {
        const onDone = jest.fn();
        render(
            <VacancyFilterStepModal
                vacancy={vacancy}
                onDone={onDone}
                onSkip={jest.fn()}
            />
        );

        fireEvent.click(await screen.findByRole('button', { name: /фильтр: москва/i }));
        fireEvent.click(screen.getByRole('button', { name: /^применить$/i }));

        await waitFor(() => {
            expect(assignFilterToVacancy).toHaveBeenCalledWith(42, 1);
            expect(onDone).toHaveBeenCalled();
        });
    });

    it('creates a new filter and assigns it', async () => {
        const onDone = jest.fn();
        assignFilterToVacancy.mockResolvedValue({ id: 42, filter_id: 9 });

        render(
            <VacancyFilterStepModal
                vacancy={vacancy}
                onDone={onDone}
                onSkip={jest.fn()}
            />
        );

        await screen.findByRole('button', { name: /фильтр: москва/i });
        fireEvent.click(screen.getByRole('button', { name: /создать новый/i }));

        const cityInput = screen.getByLabelText(/город/i);
        fireEvent.change(cityInput, { target: { value: 'Новосибирск' } });

        fireEvent.click(screen.getByRole('button', { name: /создать и применить/i }));

        await waitFor(() => {
            expect(createVacancyFilter).toHaveBeenCalledWith(
                expect.objectContaining({ city: 'Новосибирск' })
            );
            expect(assignFilterToVacancy).toHaveBeenCalledWith(42, 9);
            expect(onDone).toHaveBeenCalled();
        });
    });

    it('allows skipping filter setup', async () => {
        const onSkip = jest.fn();
        render(
            <VacancyFilterStepModal
                vacancy={vacancy}
                onDone={jest.fn()}
                onSkip={onSkip}
            />
        );

        fireEvent.click(await screen.findByRole('button', { name: /^пропустить$/i }));
        expect(onSkip).toHaveBeenCalled();
        expect(assignFilterToVacancy).not.toHaveBeenCalled();
    });

    it('switches to create mode when no filters exist', async () => {
        listVacancyFilters.mockResolvedValue([]);
        render(
            <VacancyFilterStepModal
                vacancy={vacancy}
                onDone={jest.fn()}
                onSkip={jest.fn()}
            />
        );
        expect(await screen.findByLabelText(/город/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /создать и применить/i })).toBeInTheDocument();
    });

    it('opens edit mode for assigned filter and saves PATCH', async () => {
        const onDone = jest.fn();
        render(
            <VacancyFilterStepModal
                vacancy={{ ...vacancy, filter_id: 1 }}
                allowSkip={false}
                onDone={onDone}
                onSkip={jest.fn()}
            />
        );

        expect(await screen.findByTestId('filter-save-edit')).toBeInTheDocument();
        const cityInput = screen.getByLabelText(/город/i);
        expect(cityInput).toHaveValue('Москва');

        fireEvent.change(cityInput, { target: { value: 'СПб' } });
        fireEvent.click(screen.getByTestId('filter-save-edit'));

        await waitFor(() => {
            expect(updateVacancyFilter).toHaveBeenCalledWith(
                1,
                expect.objectContaining({ city: 'СПб' })
            );
            expect(onDone).toHaveBeenCalled();
        });
    });

    it('unassigns filter in manage mode', async () => {
        const onDone = jest.fn();
        render(
            <VacancyFilterStepModal
                vacancy={{ ...vacancy, filter_id: 1 }}
                allowSkip={false}
                onDone={onDone}
                onSkip={jest.fn()}
            />
        );

        fireEvent.click(await screen.findByTestId('filter-unassign'));

        await waitFor(() => {
            expect(unassignFilterFromVacancy).toHaveBeenCalledWith(42);
            expect(onDone).toHaveBeenCalled();
        });
    });
});
