/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import HHNegotiationsModal from './HHNegotiationsModal';

const mockShowAlert = jest.fn();

jest.mock('../../context/AlertContext', () => ({
    useAlertContext: () => ({ showAlert: mockShowAlert }),
}));

jest.mock('../../services/hhImportApi', () => ({
    getHHVacancyNegotiations: jest.fn(),
    importHHNegotiation: jest.fn(),
    getHHNegotiationDetail: jest.fn(),
    executeHHNegotiationAction: jest.fn(),
}));

const {
    getHHVacancyNegotiations,
    getHHNegotiationDetail,
    executeHHNegotiationAction,
} = require('../../services/hhImportApi');

describe('HHNegotiationsModal detail + actions', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        getHHVacancyNegotiations.mockReset();
        getHHNegotiationDetail.mockReset();
        executeHHNegotiationAction.mockReset();

        getHHVacancyNegotiations.mockResolvedValue({
            items: [
                {
                    id: 'neg-1',
                    state: 'response',
                    state_name: 'Отклик',
                    created_at: '2026-08-14T10:00:00+0300',
                    resume: {
                        full_name: 'Иванов Иван',
                        title: 'Логист',
                        age: 30,
                        area: 'Москва',
                        experience_months: 24,
                        work_formats: [{ id: 'REMOTE' }],
                        alternate_url: 'https://hh.ru/resume/r1',
                    },
                },
            ],
            collections: [{ id: 'response', name: 'Неразобранные', counters: { total: 1 } }],
            collection: 'response',
            found: 1,
            pages: 1,
            page: 0,
        });

        getHHNegotiationDetail.mockResolvedValue({
            id: 'neg-1',
            hh_url: 'https://hh.ru/employer/vacancyresponses/neg-1',
            employer_state_name: 'Неразобранные',
            resume: {
                full_name: 'Иванов Иван',
                title: 'Логист',
                age: 30,
                area: 'Москва',
                experience_months: 24,
                skill_set: ['Excel'],
                alternate_url: 'https://hh.ru/resume/r1',
            },
            actions: [
                {
                    id: 'discard',
                    name: 'Отказ',
                    enabled: true,
                    arguments: [{ id: 'message', required: false }],
                },
                {
                    id: 'interview',
                    name: 'Пригласить на собеседование',
                    enabled: true,
                    arguments: [{ id: 'message', required: false }],
                },
                {
                    id: 'hired',
                    name: 'Выход на работу',
                    enabled: false,
                    arguments: [],
                },
            ],
        });
    });

    it('opens detail with HH link and enabled actions', async () => {
        render(
            <HHNegotiationsModal
                hhVacancyId="vac-1"
                vacancyName="Логист"
                onClose={jest.fn()}
            />
        );

        expect(await screen.findByText('Иванов Иван')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('negotiation-row-neg-1'));

        await waitFor(() => {
            expect(getHHNegotiationDetail).toHaveBeenCalledWith('neg-1');
        });

        const detail = await screen.findByTestId('negotiation-detail');
        expect(detail).toHaveTextContent('Москва');
        expect(screen.getByTestId('hh-external-link')).toHaveAttribute(
            'href',
            'https://hh.ru/employer/vacancyresponses/neg-1'
        );
        expect(screen.getByTestId('hh-action-discard')).toBeInTheDocument();
        expect(screen.getByTestId('hh-action-interview')).toBeInTheDocument();
        expect(screen.queryByTestId('hh-action-hired')).not.toBeInTheDocument();
    });

    it('opens full resume card without AI score', async () => {
        getHHNegotiationDetail.mockResolvedValue({
            id: 'neg-1',
            hh_url: 'https://hh.ru/employer/vacancyresponses/neg-1',
            employer_state_name: 'Неразобранные',
            resume: {
                full_name: 'Иванов Иван',
                last_name: 'Иванов',
                first_name: 'Иван',
                title: 'Логист',
                age: 30,
                birth_date: '1996-05-01',
                area: 'Москва',
                experience_months: 24,
                skill_set: ['Excel'],
                experience: [{ title: 'Логист', company: 'ООО Ромашка', period: '2022 — н.в.' }],
                education: ['МГУ'],
                alternate_url: 'https://hh.ru/resume/r1',
            },
            actions: [],
        });

        render(
            <HHNegotiationsModal
                hhVacancyId="vac-1"
                vacancyName="Логист"
                onClose={jest.fn()}
            />
        );

        fireEvent.click(await screen.findByTestId('negotiation-row-neg-1'));
        fireEvent.click(await screen.findByTestId('negotiation-resume-open'));

        const card = await screen.findByTestId('negotiation-resume-modal');
        expect(card).toHaveTextContent('Карточка кандидата');
        expect(card).toHaveTextContent('Иванов Иван');
        expect(card).toHaveTextContent('О кандидате');
        expect(card).toHaveTextContent('ООО Ромашка');
        expect(card).toHaveTextContent('Оценка AI появится');
        expect(card).not.toHaveTextContent('/ 100');
        expect(screen.queryByTestId('candidate-ai-score')).not.toBeInTheDocument();
    });

    it('runs discard via HH action API with optional message', async () => {
        executeHHNegotiationAction.mockResolvedValue({
            status: 'ok',
            action_id: 'discard',
            negotiation: {
                id: 'neg-1',
                employer_state: 'discard',
                employer_state_name: 'Отказ',
                resume: { full_name: 'Иванов Иван', title: 'Логист' },
                actions: [],
                hh_url: 'https://hh.ru/employer/vacancyresponses/neg-1',
            },
        });

        render(
            <HHNegotiationsModal
                hhVacancyId="vac-1"
                vacancyName="Логист"
                onClose={jest.fn()}
            />
        );

        fireEvent.click(await screen.findByTestId('negotiation-row-neg-1'));
        fireEvent.click(await screen.findByTestId('hh-action-discard'));

        expect(await screen.findByTestId('action-message-form')).toBeInTheDocument();
        fireEvent.change(screen.getByPlaceholderText(/текст сообщения/i), {
            target: { value: 'К сожалению, не подходите' },
        });
        fireEvent.click(screen.getByRole('button', { name: /подтвердить/i }));

        await waitFor(() => {
            expect(executeHHNegotiationAction).toHaveBeenCalledWith('neg-1', 'discard', {
                arguments: { message: 'К сожалению, не подходите' },
            });
        });
        expect(mockShowAlert).toHaveBeenCalledWith(
            expect.stringMatching(/выполнено на HH/i),
            'success'
        );
    });

    it('filters list by city age experience and work format', async () => {
        getHHVacancyNegotiations.mockResolvedValue({
            items: [
                {
                    id: 'neg-1',
                    state: 'response',
                    state_name: 'Отклик',
                    resume: {
                        full_name: 'Иванов Иван',
                        area: 'Москва',
                        age: 30,
                        experience_months: 40,
                        work_formats: [{ id: 'REMOTE' }],
                    },
                },
                {
                    id: 'neg-2',
                    state: 'response',
                    state_name: 'Отклик',
                    resume: {
                        full_name: 'Петров Пётр',
                        area: 'Казань',
                        age: 45,
                        experience_months: 8,
                        work_formats: [{ id: 'ON_SITE' }],
                    },
                },
            ],
            collections: [{ id: 'response', name: 'Неразобранные', counters: { total: 2 } }],
            collection: 'response',
            found: 2,
            pages: 1,
            page: 0,
        });

        render(
            <HHNegotiationsModal hhVacancyId="vac-1" vacancyName="Логист" onClose={jest.fn()} />
        );

        expect(await screen.findByTestId('negotiation-row-neg-1')).toBeInTheDocument();
        expect(screen.getByTestId('negotiation-row-neg-2')).toBeInTheDocument();

        fireEvent.change(screen.getByTestId('filter-city'), { target: { value: 'Москва' } });
        expect(screen.getByTestId('negotiation-row-neg-1')).toBeInTheDocument();
        expect(screen.queryByTestId('negotiation-row-neg-2')).not.toBeInTheDocument();

        fireEvent.click(screen.getByTestId('filter-reset'));
        fireEvent.change(screen.getByTestId('filter-age-from'), { target: { value: '40' } });
        expect(screen.queryByTestId('negotiation-row-neg-1')).not.toBeInTheDocument();
        expect(screen.getByTestId('negotiation-row-neg-2')).toBeInTheDocument();

        fireEvent.click(screen.getByTestId('filter-reset'));
        fireEvent.change(screen.getByTestId('filter-experience'), { target: { value: 'between1And3' } });
        expect(screen.getByTestId('negotiation-row-neg-1')).toBeInTheDocument();
        expect(screen.queryByTestId('negotiation-row-neg-2')).not.toBeInTheDocument();

        fireEvent.click(screen.getByTestId('filter-reset'));
        fireEvent.change(screen.getByTestId('filter-work-format'), { target: { value: 'office' } });
        expect(screen.queryByTestId('negotiation-row-neg-1')).not.toBeInTheDocument();
        expect(screen.getByTestId('negotiation-row-neg-2')).toBeInTheDocument();
    });
});
