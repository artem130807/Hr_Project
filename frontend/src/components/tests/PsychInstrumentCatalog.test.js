/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import PsychInstrumentCatalog from './PsychInstrumentCatalog';

const mockShowAlert = jest.fn();
const writeText = jest.fn().mockResolvedValue(undefined);

Object.assign(navigator, {
    clipboard: { writeText },
});

jest.mock('../../context/AlertContext', () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));

jest.mock('../../services/psychTestApi', () => ({
    listPsychInstruments: jest.fn(),
}));

const { listPsychInstruments } = require('../../services/psychTestApi');

describe('PsychInstrumentCatalog', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        writeText.mockClear();
        listPsychInstruments.mockReset();
        listPsychInstruments.mockResolvedValue({
            items: [
                {
                    id: 'complex_work_behavior_220',
                    name: 'Комплексный опросник',
                    version: '1.0',
                    item_count: 220,
                    duration_minutes: '35–45',
                    description: 'Пилот',
                },
            ],
        });
    });

    it('shows instrument and copies take link', async () => {
        render(<PsychInstrumentCatalog />);
        expect(await screen.findByTestId('psych-instrument-catalog')).toBeInTheDocument();
        expect(screen.getByText('Комплексный опросник')).toBeInTheDocument();

        fireEvent.click(screen.getByTestId('copy-psych-link-complex_work_behavior_220'));
        await waitFor(() => {
            expect(writeText).toHaveBeenCalledWith(
                expect.stringMatching(/\/take\/complex_work_behavior_220$/)
            );
        });
        expect(mockShowAlert).toHaveBeenCalledWith('Ссылка скопирована', 'success');
    });
});
