/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ProfessionalTakePage from './ProfessionalTakePage';

jest.mock(
    'react-router-dom',
    () => ({
        useParams: () => ({ testId: '10' }),
    }),
    { virtual: true }
);

jest.mock('../services/publicProfessionalTestApi', () => ({
    getPublicProfessionalTest: jest.fn(),
    submitPublicProfessionalResult: jest.fn(),
}));

const {
    getPublicProfessionalTest,
    submitPublicProfessionalResult,
} = require('../services/publicProfessionalTestApi');

describe('ProfessionalTakePage', () => {
    beforeEach(() => {
        getPublicProfessionalTest.mockReset();
        submitPublicProfessionalResult.mockReset();
        getPublicProfessionalTest.mockResolvedValue({
            id: 10,
            name: 'Тест логиста',
            instruction: 'Ответьте кратко',
            duration_minutes: 30,
            questions: [
                { id: 1, text: 'Что такое логистика?', options: ['A', 'B'] },
                { id: 2, text: 'Опишите маршрут', options: ['X', 'Y'] },
            ],
        });
        submitPublicProfessionalResult.mockResolvedValue({
            id: 5,
            score: 1,
            max_score: 2,
        });
    });

    it('intro → start → one question at a time → submit', async () => {
        render(<ProfessionalTakePage />);
        expect(await screen.findByTestId('prof-take-page')).toBeInTheDocument();
        expect(screen.getByText('Тест логиста')).toBeInTheDocument();

        fireEvent.change(screen.getByTestId('prof-full-name'), { target: { value: 'Иванов Иван' } });
        fireEvent.change(screen.getByTestId('prof-position'), { target: { value: 'Логист' } });
        fireEvent.click(screen.getByTestId('prof-start'));

        expect(await screen.findByTestId('prof-question-1')).toBeInTheDocument();
        expect(screen.queryByTestId('prof-question-2')).not.toBeInTheDocument();
        expect(screen.getByTestId('prof-timer')).toBeInTheDocument();

        fireEvent.click(screen.getByTestId('prof-option-1'));
        fireEvent.click(screen.getByTestId('prof-next'));

        expect(await screen.findByTestId('prof-question-2')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('prof-option-0'));
        fireEvent.click(screen.getByTestId('prof-next'));

        await waitFor(() => {
            expect(submitPublicProfessionalResult).toHaveBeenCalled();
        });
        const payload = submitPublicProfessionalResult.mock.calls[0][0];
        expect(payload.test_id).toBe(10);
        expect(payload.full_name).toBe('Иванов Иван');
        expect(payload.answers['1'].option_index).toBe(1);
        expect(payload.answers['2'].option_index).toBe(0);
        expect(payload.answers['1'].forced_incorrect).toBe(false);
        const done = await screen.findByTestId('prof-take-done');
        expect(done).toHaveTextContent('Спасибо!');
        expect(done).toHaveTextContent('Ответы сохранены.');
        expect(done).not.toHaveTextContent('Результаты доступны');
    });

    it('keeps Next control inside integrity zone', async () => {
        render(<ProfessionalTakePage />);
        fireEvent.change(await screen.findByTestId('prof-full-name'), {
            target: { value: 'Сидоров' },
        });
        fireEvent.change(screen.getByTestId('prof-position'), { target: { value: 'Логист' } });
        fireEvent.click(screen.getByTestId('prof-start'));

        const zone = await screen.findByTestId('prof-integrity-zone');
        expect(zone.contains(screen.getByTestId('prof-next'))).toBe(true);
    });

    it('does not re-lock already violated question on repeated mouse leave', async () => {
        render(<ProfessionalTakePage />);
        fireEvent.change(await screen.findByTestId('prof-full-name'), {
            target: { value: 'Петров' },
        });
        fireEvent.change(screen.getByTestId('prof-position'), { target: { value: 'Логист' } });
        fireEvent.click(screen.getByTestId('prof-start'));

        const zone = await screen.findByTestId('prof-integrity-zone');
        fireEvent.mouseLeave(zone);
        fireEvent.mouseLeave(zone);
        fireEvent.click(screen.getByTestId('prof-next'));
        await screen.findByTestId('prof-question-2');
        fireEvent.click(screen.getByTestId('prof-option-0'));
        fireEvent.click(screen.getByTestId('prof-next'));

        await waitFor(() => expect(submitPublicProfessionalResult).toHaveBeenCalled());
        const integrity = submitPublicProfessionalResult.mock.calls[0][0].integrity;
        expect(integrity.mouse_leave_count).toBe(1);
    });

    it('mouse leave locks current question as incorrect', async () => {
        render(<ProfessionalTakePage />);
        fireEvent.change(await screen.findByTestId('prof-full-name'), {
            target: { value: 'Петров' },
        });
        fireEvent.change(screen.getByTestId('prof-position'), { target: { value: 'Логист' } });
        fireEvent.click(screen.getByTestId('prof-start'));

        await screen.findByTestId('prof-integrity-zone');
        fireEvent.mouseLeave(screen.getByTestId('prof-integrity-zone'));
        expect(await screen.findByTestId('prof-integrity-warning')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('prof-next'));

        await screen.findByTestId('prof-question-2');
        fireEvent.click(screen.getByTestId('prof-option-0'));
        fireEvent.click(screen.getByTestId('prof-next'));

        await waitFor(() => expect(submitPublicProfessionalResult).toHaveBeenCalled());
        const answers = submitPublicProfessionalResult.mock.calls[0][0].answers;
        expect(answers['1'].forced_incorrect).toBe(true);
        expect(answers['1'].violations).toContain('mouse_leave');
    });

    it('hides identity fields when test is linked to a candidate', async () => {
        window.history.pushState({}, "", "/take/test/10?candidate_id=6&result_id=2");
        render(<ProfessionalTakePage />);
        expect(await screen.findByTestId("prof-take-page")).toBeInTheDocument();
        expect(screen.queryByTestId("prof-full-name")).not.toBeInTheDocument();
        expect(screen.queryByText(/связан с вашей карточкой/i)).not.toBeInTheDocument();
        fireEvent.click(screen.getByTestId("prof-start"));
        expect(await screen.findByTestId("prof-question-1")).toBeInTheDocument();
        fireEvent.click(screen.getByTestId("prof-option-0"));
        fireEvent.click(screen.getByTestId("prof-next"));
        fireEvent.click(await screen.findByTestId("prof-option-0"));
        fireEvent.click(screen.getByTestId("prof-next"));
        await waitFor(() => expect(submitPublicProfessionalResult).toHaveBeenCalled());
        const payload = submitPublicProfessionalResult.mock.calls[0][0];
        expect(payload.candidate_id).toBe(6);
        expect(payload.result_id).toBe(2);
        expect(payload.full_name).toBeUndefined();
        expect(payload.position).toBeUndefined();
    });
});
