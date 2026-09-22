/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import VacancyTestsManager, {
    normalizeIdList,
    normalizeTests,
} from './VacancyTestsManager';

const mockShowAlert = jest.fn();

jest.mock('../../context/AlertContext', () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));

jest.mock('../../services/testApi', () => ({
    getTests: jest.fn(),
    getTestForVacancy: jest.fn(),
    updateTestForVacancy: jest.fn(),
}));

const {
    getTests,
    getTestForVacancy,
    updateTestForVacancy,
} = require('../../services/testApi');

describe('normalize helpers', () => {
    it('normalizeIdList accepts ints and objects', () => {
        expect(normalizeIdList([1, { id: 2 }, { test_id: 3 }])).toEqual([1, 2, 3]);
        expect(normalizeIdList({ items: [4] })).toEqual([4]);
    });

    it('normalizeTests filters invalid rows', () => {
        expect(normalizeTests([{ id: 1, name: 'A' }, { name: 'no id' }])).toEqual([
            { id: 1, name: 'A' },
        ]);
    });
});

describe('VacancyTestsManager', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        getTests.mockReset();
        getTestForVacancy.mockReset();
        updateTestForVacancy.mockReset();
        getTests.mockResolvedValue([
            {
                id: 1,
                name: 'Профтест',
                description: 'Описание',
                test_type: 'Вопросно-ответная форма',
                results_type: 'текстовый результат',
            },
            { id: 2, name: 'URL тест', test_type: 'url', results_type: 'скриншот' },
        ]);
        getTestForVacancy.mockResolvedValue([1]);
        updateTestForVacancy.mockResolvedValue([1, 2]);
    });

    it('loads and shows selected tests', async () => {
        render(
            <VacancyTestsManager
                vacancyId={42}
                vacancyName="Логист"
                onClose={jest.fn()}
            />
        );
        expect(await screen.findByTestId('vacancy-test-option-1')).toBeInTheDocument();
        expect(screen.getByText(/Тесты для вакансии «Логист»/)).toBeInTheDocument();
        expect(screen.getByTestId('vacancy-test-option-1').querySelector('input')).toBeChecked();
        expect(screen.getByTestId('vacancy-test-option-2').querySelector('input')).not.toBeChecked();
    });

    it('saves toggled selection via updateTestForVacancy', async () => {
        const onClose = jest.fn();
        render(
            <VacancyTestsManager vacancyId={42} vacancyName="Логист" onClose={onClose} />
        );
        await screen.findByTestId('vacancy-test-option-2');
        fireEvent.click(screen.getByTestId('vacancy-test-option-2').querySelector('input'));
        fireEvent.click(screen.getByTestId('vacancy-tests-save'));
        await waitFor(() =>
            expect(updateTestForVacancy).toHaveBeenCalledWith(42, expect.arrayContaining([1, 2]))
        );
        expect(onClose).toHaveBeenCalled();
        expect(mockShowAlert).toHaveBeenCalledWith(expect.stringMatching(/Привязано/), 'success');
    });

    it('handles empty linked tests without error', async () => {
        getTestForVacancy.mockResolvedValue([]);
        render(<VacancyTestsManager vacancyId={7} onClose={jest.fn()} />);
        await screen.findByTestId('vacancy-test-option-1');
        expect(screen.getByText(/Выбрано:/).textContent).toMatch(/0/);
    });
});
