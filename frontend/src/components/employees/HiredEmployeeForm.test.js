/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import HiredEmployeeForm from './HiredEmployeeForm';

describe('HiredEmployeeForm', () => {
    it('submits required fields', async () => {
        const onSubmit = jest.fn().mockResolvedValue({});
        const onClose = jest.fn();
        render(<HiredEmployeeForm onClose={onClose} onSubmit={onSubmit} />);

        fireEvent.change(screen.getByTestId('employee-full-name'), {
            target: { value: 'Сидоров Пётр' },
        });
        fireEvent.change(screen.getByTestId('employee-position'), {
            target: { value: 'Водитель' },
        });
        fireEvent.change(screen.getByTestId('employee-department'), {
            target: { value: 'логистический' },
        });
        fireEvent.change(screen.getByTestId('employee-adaptation-route'), {
            target: { value: 'full' },
        });
        fireEvent.click(screen.getByTestId('employee-submit'));

        await waitFor(() => expect(onSubmit).toHaveBeenCalled());
        expect(onSubmit.mock.calls[0][0]).toEqual(
            expect.objectContaining({
                full_name: 'Сидоров Пётр',
                position: 'Водитель',
                department: 'логистический',
                adaptation_route: 'full',
            })
        );
    });

    it('blocks submit without required fields', async () => {
        const onSubmit = jest.fn();
        render(<HiredEmployeeForm onClose={jest.fn()} onSubmit={onSubmit} />);
        fireEvent.click(screen.getByTestId('employee-submit'));
        expect(await screen.findByRole('alert')).toHaveTextContent(/ФИО/i);
        expect(onSubmit).not.toHaveBeenCalled();
    });
});
