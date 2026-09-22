import * as XLSX from 'xlsx';
import { exportEmployeesToExcel, importEmployeesFromExcel } from './excelUtils';

jest.mock('xlsx', () => ({
    __esModule: true,
    utils: {
        json_to_sheet: jest.fn(() => ({})),
        book_new: jest.fn(() => ({})),
        book_append_sheet: jest.fn(),
        sheet_to_json: jest.fn(() => [
            { Логин: 'ivan', Пароль: 'pass', Имя: 'Ivan', Роль: 'hr' },
        ]),
    },
    writeFile: jest.fn(),
    read: jest.fn(() => ({
        SheetNames: ['Sheet1'],
        Sheets: { Sheet1: {} },
    })),
}));

describe('excelUtils', () => {
    it('exportEmployeesToExcel пишет файл с full_name', () => {
        exportEmployeesToExcel([
            { id: 1, full_name: 'Ivan', username: 'ivan', role: 'hr', created_at: '2026-01-01' },
        ]);
        expect(XLSX.utils.json_to_sheet).toHaveBeenCalledWith([
            expect.objectContaining({ Имя: 'Ivan', Логин: 'ivan', Пароль: '', Роль: 'hr' }),
        ]);
        expect(XLSX.writeFile.mock.calls[0][1]).toMatch(/^Сотрудники — \d{4}-\d{2}-\d{2}\.xlsx$/);
    });

    it('importEmployeesFromExcel вызывает readAsArrayBuffer после onload', () => {
        let readCalled = false;
        const originalFileReader = global.FileReader;

        class MockFileReader {
            constructor() {
                this._onload = null;
                this.onerror = null;
            }
            set onload(fn) {
                this._onload = fn;
            }
            get onload() {
                return this._onload;
            }
            readAsArrayBuffer() {
                readCalled = true;
            }
        }
        global.FileReader = MockFileReader;

        importEmployeesFromExcel(new Blob(['fake']));
        expect(readCalled).toBe(true);

        global.FileReader = originalFileReader;
    });
});
