/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import PsychTakePage from './PsychTakePage';

jest.mock(
    'react-router-dom',
    () => ({
        useParams: () => ({ instrumentId: 'complex_work_profile' }),
    }),
    { virtual: true }
);

jest.mock('../services/psychTestApi', () => ({
    getPublicPsychInstrument: jest.fn(),
    submitPublicPsychResult: jest.fn(),
}));

const {
    getPublicPsychInstrument,
    submitPublicPsychResult,
} = require('../services/psychTestApi');

describe('PsychTakePage', () => {
    beforeEach(() => {
        sessionStorage.clear();
        localStorage.clear();
        getPublicPsychInstrument.mockReset();
        submitPublicPsychResult.mockReset();
        getPublicPsychInstrument.mockResolvedValue({
            id: 'complex_work_profile',
            name: 'Комплексная оценка рабочего профиля',
            instruction: 'Отвечайте честно',
            answer_scale: { labels: { 1: 'нет', 5: 'да' } },
            presentation: {
                scheme: '231',
                block_order: ['avp', 'sjt', 'disc'],
                shuffle_modules: ['avp'],
                block_count: 3,
            },
            items: [
                {
                    num: 1,
                    code: 'DISC-01',
                    module: 'disc',
                    prompt: 'В обычной рабочей ситуации',
                    options: { A: 'решительный', B: 'общительный', C: 'спокойный', D: 'точный' },
                },
                {
                    num: 2,
                    code: 'AVP-001',
                    module: 'avp',
                    text: 'Легко заводите друзей',
                },
            ],
        });
        submitPublicPsychResult.mockResolvedValue({ id: 9 });
    });

    it('starts from original block 2 (AVP) then original block 1 (DISC)', async () => {
        render(<PsychTakePage />);

        expect(await screen.findByTestId('psych-take-page')).toBeInTheDocument();
        expect(screen.getByText(/Блок 1 из 3/)).toBeInTheDocument();
        const first = screen.getByTestId('psych-item-2');
        expect(first).toHaveTextContent('Легко заводите друзей');
        expect(screen.queryByTestId('psych-submit')).not.toBeInTheDocument();

        fireEvent.change(screen.getByTestId('psych-full-name'), {
            target: { value: 'Иванов Иван' },
        });
        fireEvent.change(screen.getByTestId('psych-position'), {
            target: { value: 'Логист' },
        });
        fireEvent.change(screen.getByTestId('psych-birth-date'), {
            target: { value: '1998-08-12' },
        });
        expect(screen.getByTestId('psych-taken-at')).toHaveValue(
            `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}-${String(new Date().getDate()).padStart(2, '0')}`
        );

        fireEvent.click(first.querySelectorAll('button')[2]);

        const second = await screen.findByTestId('psych-item-1');
        expect(second).toHaveTextContent('решительный');
        expect(screen.getByText(/Блок 3 из 3/)).toBeInTheDocument();
        const discButtons = second.querySelectorAll('button');
        fireEvent.click(discButtons[0]);
        fireEvent.click(discButtons[5]);

        await waitFor(() => {
            expect(screen.getByTestId('psych-submit')).toBeInTheDocument();
        });
        fireEvent.click(screen.getByTestId('psych-submit'));

        await waitFor(() => {
            expect(submitPublicPsychResult).toHaveBeenCalledWith(
                expect.objectContaining({
                    instrument_id: 'complex_work_profile',
                    full_name: 'Иванов Иван',
                    answers: {
                        'DISC-01': { most: 'A', least: 'B' },
                        'AVP-001': 3,
                    },
                    birth_date: '1998-08-12',
                    timing: expect.objectContaining({
                        presentation: expect.objectContaining({
                            item_order: ['AVP-001', 'DISC-01'],
                        }),
                    }),
                })
            );
        });
        expect(await screen.findByTestId('psych-take-done')).toBeInTheDocument();
        expect(sessionStorage.getItem('psych-take-presentation:complex_work_profile')).toBeNull();
        expect(localStorage.getItem('psych-take-draft:v1:complex_work_profile:anon')).toBeNull();
    });

    it('restores answers and question after remount', async () => {
        const { unmount } = render(<PsychTakePage />);
        const first = await screen.findByTestId('psych-item-2');
        fireEvent.click(first.querySelectorAll('button')[2]);
        await screen.findByTestId('psych-item-1');
        unmount();

        render(<PsychTakePage />);
        expect(await screen.findByTestId('psych-item-1')).toHaveTextContent('решительный');
        expect(screen.getByText(/Задание 2 из 2/)).toBeInTheDocument();
        const disc = screen.getByTestId('psych-item-1');
        const discButtons = disc.querySelectorAll('button');
        fireEvent.click(discButtons[0]);
        fireEvent.click(discButtons[5]);
        fireEvent.change(await screen.findByTestId('psych-full-name'), { target: { value: 'Петров' } });
        fireEvent.change(screen.getByTestId('psych-position'), { target: { value: 'HR' } });
        fireEvent.change(screen.getByTestId('psych-birth-date'), { target: { value: '1990-01-02' } });
        await waitFor(() => expect(screen.getByTestId('psych-submit')).toBeInTheDocument());
        fireEvent.click(screen.getByTestId('psych-submit'));
        await waitFor(() => {
            expect(submitPublicPsychResult).toHaveBeenCalledWith(
                expect.objectContaining({
                    answers: {
                        'DISC-01': { most: 'A', least: 'B' },
                        'AVP-001': 3,
                    },
                })
            );
        });
    });

    it('blocks next question without answer', async () => {
        render(<PsychTakePage />);
        expect(await screen.findByTestId('psych-take-page')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Далее'));
        expect(screen.getByRole('alert')).toHaveTextContent('1–5');
        expect(screen.getByTestId('psych-item-2')).toBeInTheDocument();
    });

    it('supports keyboard quick input with digits on AVP', async () => {
        render(<PsychTakePage />);
        await screen.findByTestId('psych-item-2');
        fireEvent.keyDown(window, { key: '4' });
        const disc = await screen.findByTestId('psych-item-1');
        expect(disc).toHaveTextContent('решительный');
    });
});
