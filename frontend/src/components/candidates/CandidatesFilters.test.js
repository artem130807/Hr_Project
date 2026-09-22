/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import CandidatesFilters from './CandidatesFilters';

jest.mock(
    'react-router-dom',
    () => ({
        Link: ({ children, to }) => <a href={to}>{children}</a>,
    }),
    { virtual: true }
);

jest.mock('../hh/AutoNegotiationsToggle', () => () => null);

describe('CandidatesFilters', () => {
    const base = {
        searchQuery: '',
        onSearchChange: jest.fn(),
        statusFilter: null,
        statusDict: [{ id: 1, code: 'откликнулся', name: 'откликнулся' }],
        onStatusChange: jest.fn(),
        vacancyOptions: [
            { id: 10, name: 'Логист HH', hh_vacancy_id: '1' },
            { id: 11, name: 'Водитель HH', hh_vacancy_id: '2' },
        ],
        selectedVacancyIds: [],
        onToggleVacancy: jest.fn(),
        onClearVacancies: jest.fn(),
        vacanciesLoading: false,
        unboundHhCount: 0,
        categoryFilter: 'candidate',
        onCategoryChange: jest.fn(),
        onlyPerfect: false,
        onOnlyPerfectChange: jest.fn(),
    };

    it('renders HH vacancy checkboxes and toggles', () => {
        render(<CandidatesFilters {...base} />);
        expect(screen.getByTestId('candidates-vacancy-filter')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('vacancy-option-10'));
        expect(base.onToggleVacancy).toHaveBeenCalledWith(10);
    });

    it('shows clear when selection present', () => {
        render(<CandidatesFilters {...base} selectedVacancyIds={[10]} />);
        fireEvent.click(screen.getByTestId('candidates-vacancy-clear'));
        expect(base.onClearVacancies).toHaveBeenCalled();
    });

    it('explains unbound HH vacancies in empty state', () => {
        render(<CandidatesFilters {...base} vacancyOptions={[]} unboundHhCount={3} />);
        expect(screen.getByTestId('candidates-vacancy-empty')).toHaveTextContent(
            /ещё не привязаны к платформе/
        );
        expect(screen.getByRole('link', { name: /Импортировать/i })).toHaveAttribute(
            'href',
            '/vacancies?tab=hh'
        );
    });
});
