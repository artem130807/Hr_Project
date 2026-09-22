/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import PsychResultsPage from './PsychResultsPage';

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
        user: { id: 1, role: 'hr', username: 'hr' },
        logout: jest.fn(),
    }),
}));

jest.mock('../services/psychTestApi', () => ({
    listPsychResults: jest.fn(),
    getPsychResult: jest.fn(),
}));

jest.mock('../services/publicProfessionalTestApi', () => ({
    listPublicProfessionalResults: jest.fn(),
    getPublicProfessionalResult: jest.fn(),
}));

jest.mock('../services/userApi', () => ({ getInviteUrl: jest.fn() }));
jest.mock('../services/hhAuthApi', () => ({
    checkHHAuth: jest.fn(() => Promise.resolve({ auth_passed: true })),
    getHHAuthLink: jest.fn(() => Promise.resolve('https://hh.example/auth')),
}));
jest.mock('../components/sidebar/AutoSelectSection', () => () => null);
jest.mock('../components/notifications/NotificationBell', () => () => null);

const { listPsychResults, getPsychResult } = require('../services/psychTestApi');
const {
    listPublicProfessionalResults,
    getPublicProfessionalResult,
} = require('../services/publicProfessionalTestApi');

describe('PsychResultsPage', () => {
    beforeEach(() => {
        mockShowAlert.mockReset();
        listPsychResults.mockReset();
        getPsychResult.mockReset();
        listPublicProfessionalResults.mockReset();
        getPublicProfessionalResult.mockReset();
        listPsychResults.mockResolvedValue([
            {
                id: 3,
                full_name: 'Петров Пётр',
                position: 'Водитель',
                taken_at: '2026-08-14',
                quality_status: 'Допустим',
                leading_disc: 'Доминирование / напор',
                leading_paei: 'Производитель результата',
                chs: 3,
                chm: 2,
            },
        ]);
        listPublicProfessionalResults.mockResolvedValue([
            {
                id: 9,
                test_id: 42,
                test_name: 'Тест логиста',
                full_name: 'Иванов Иван',
                position: 'Логист',
                taken_at: '2026-08-13',
                score: 1,
                max_score: 2,
                timed_out: false,
            },
        ]);
        getPsychResult.mockResolvedValue({
            id: 3,
            full_name: "Петров Пётр",
            position: "Водитель",
            taken_at: "2026-08-14",
            quality_status: "Приемлемый протокол",
            leading_disc: "D",
            leading_paei: "Производитель результата",
            leading_work10: "Устойчивость",
            birth_date: "1998-08-12",
            chs: 3,
            chm: 2,
            scores: {
                quality: { active_duration_sec: 1680, status: "Приемлемый протокол" },
                disc: {
                    "В работе": [
                        { code: "D", name: "D", raw: 4, score: 75 },
                        { code: "I", raw: -1, score: 44 },
                        { code: "S", raw: -2, score: 38 },
                        { code: "C", raw: 1, score: 56 },
                    ],
                    "Под давлением": [{ code: "D", raw: 7, score: 94 }],
                    Личное: [{ code: "D", raw: 3, score: 69 }],
                },
                paei: [
                    { code: "P", name: "Производитель результата", count: 8, score: 33 },
                    { code: "A", name: "Администратор", count: 5, score: 21 },
                    { code: "E", name: "Предприниматель", count: 6, score: 25 },
                    { code: "I", name: "Интегратор", count: 5, score: 21 },
                ],
                avp: {
                    factors: [
                        { code: "E", name: "Экстраверсия", score: 53 },
                        { code: "A", name: "Доброжелательность", score: 48 },
                        { code: "C", name: "Добросовестность", score: 42 },
                        { code: "ES", name: "Эмоциональная стабильность", score: 47 },
                        { code: "O", name: "Открытость и интеллект", score: 86 },
                    ],
                    aspects: [{ code: "Ee", name: "Устойчивость", score: 55 }],
                },
                sjt: { quality_index: 79, sum: 57, max: 72 },
            },
        });
        getPublicProfessionalResult.mockResolvedValue({
            id: 9,
            test_id: 42,
            test_name: 'Тест логиста',
            full_name: 'Иванов Иван',
            position: 'Логист',
            taken_at: '2026-08-13',
            score: 1,
            max_score: 2,
            timed_out: false,
            integrity: { tab_blur_count: 1, mouse_leave_count: 0 },
            answers: {
                1: {
                    value: 'Ответ А',
                    option_index: 0,
                    is_correct: true,
                    forced_incorrect: false,
                    violations: [],
                },
                2: {
                    value: 'Ответ Б',
                    option_index: 1,
                    is_correct: false,
                    forced_incorrect: true,
                    violations: ['tab_blur'],
                },
            },
        });
    });

    it('lists psych and professional results and opens psych detail', async () => {
        render(<PsychResultsPage />);
        expect(await screen.findByTestId('psych-results-table')).toBeInTheDocument();
        expect(screen.getByText('Петров Пётр')).toBeInTheDocument();
        expect(screen.getByText('Иванов Иван')).toBeInTheDocument();
        expect(screen.getByText('Тест логиста')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /подробнее/i }));
        await waitFor(() => expect(getPsychResult).toHaveBeenCalledWith(3));
        const detail = await screen.findByTestId('psych-result-detail');
        expect(detail).toHaveTextContent(/отчёт по результатам оценки кандидата/i);
        expect(detail).toHaveTextContent('Пять факторов BFAS');
        expect(detail).toHaveTextContent(/внутренний пилотный поведенческий блок/);
        expect(detail).toHaveTextContent(/внутренний SJT, пилотная версия/);
        expect(detail).not.toHaveTextContent(/DISC|PAEI|ведущий тип|Производитель результата|Администратор|Предприниматель|Интегратор/i);
        expect(detail).toHaveTextContent('Приемлемый протокол');
        expect(detail).toHaveTextContent('Устойчивость');
        expect(detail).not.toHaveTextContent('matrix');
        expect(detail).not.toHaveTextContent('priorities');
        expect(screen.getByTestId('psych-save-pdf')).toHaveTextContent('Сохранить PDF');
        expect(screen.getByTestId('psych-chs')).toHaveTextContent('3');
        expect(screen.getByTestId('psych-chm')).toHaveTextContent('2');
    });

    it('filters by type and applies FIO / specialty search', async () => {
        render(<PsychResultsPage />);
        await screen.findByTestId('psych-results-table');

        fireEvent.change(screen.getByTestId('filter-test-type'), {
            target: { value: 'professional' },
        });
        await waitFor(() => {
            expect(listPublicProfessionalResults).toHaveBeenCalled();
            expect(listPsychResults).toHaveBeenCalledTimes(1);
        });

        fireEvent.change(screen.getByTestId('filter-fio'), { target: { value: 'Иванов' } });
        fireEvent.change(screen.getByTestId('filter-specialty'), { target: { value: 'Логист' } });
        fireEvent.click(screen.getByTestId('filter-apply'));

        await waitFor(() => {
            expect(listPublicProfessionalResults).toHaveBeenCalledWith(
                expect.objectContaining({ q: 'Иванов', position: 'Логист' })
            );
        });
    });

    it('opens professional result answers', async () => {
        render(<PsychResultsPage />);
        await screen.findByText('Иванов Иван');
        expect(screen.getByText('1/2')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /открыть/i }));
        await waitFor(() => expect(getPublicProfessionalResult).toHaveBeenCalledWith(9));
        const detail = await screen.findByTestId('prof-result-answers');
        expect(detail).toHaveTextContent('Ответ А');
        expect(detail).toHaveTextContent('Ответ Б');
        expect(screen.getByTestId('prof-result-score')).toHaveTextContent('1 / 2');
        expect(screen.getByTestId('prof-result-integrity')).toHaveTextContent('вкладка 1');
        expect(detail).not.toHaveTextContent('[object Object]');
        expect(screen.getByTestId('prof-save-pdf')).toHaveTextContent('Сохранить PDF');
    });
});
