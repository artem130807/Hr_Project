/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import TestList from './TestList';

const mockShowAlert = jest.fn();
const writeText = jest.fn().mockResolvedValue(undefined);

Object.assign(navigator, {
    clipboard: { writeText },
});

jest.mock('../../context/AlertContext', () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));

describe('TestList professional copy link', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        writeText.mockClear();
    });

    it('copies public take link for Q&A professional tests', async () => {
        render(
            <TestList
                tests={[
                    {
                        id: 42,
                        name: 'Тест логиста',
                        test_type: 'Вопросно-ответная форма',
                        results_type: 'текстовый результат',
                        description: 'Проф',
                    },
                ]}
                onTestDeleted={jest.fn()}
                onTestClick={jest.fn()}
            />
        );

        fireEvent.click(screen.getByTestId('copy-prof-link-42'));
        await waitFor(() => {
            expect(writeText).toHaveBeenCalledWith(expect.stringMatching(/\/take\/test\/42$/));
        });
        expect(mockShowAlert).toHaveBeenCalledWith('Ссылка скопирована', 'success');
    });

    it('does not show copy link for URL tests', () => {
        render(
            <TestList
                tests={[
                    {
                        id: 7,
                        name: 'Внешний',
                        test_type: 'url',
                        results_type: 'результат обрабатывается сторонним сервисом',
                        url: 'https://example.com',
                    },
                ]}
                onTestDeleted={jest.fn()}
                onTestClick={jest.fn()}
            />
        );
        expect(screen.queryByTestId('copy-prof-link-7')).not.toBeInTheDocument();
    });
});
