const storage = new Map();

beforeEach(() => {
    storage.clear();
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => (
        storage.has(key) ? storage.get(key) : null
    ));
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation((key, value) => {
        storage.set(String(key), String(value));
    });
    jest.spyOn(Storage.prototype, 'removeItem').mockImplementation((key) => {
        storage.delete(String(key));
    });
    jest.spyOn(console, 'log').mockImplementation(() => {});
});

afterEach(() => {
    jest.restoreAllMocks();
});

import { loadCandidates, saveCandidates } from './localStorageHelper';

describe('localStorageHelper', () => {
    describe('loadCandidates', () => {
        it('должен загружать кандидатов из localStorage', () => {
            const candidates = [
                { id: 1, name: 'John Doe' },
                { id: 2, name: 'Jane Smith' },
            ];
            storage.set('candidates', JSON.stringify(candidates));

            expect(loadCandidates()).toEqual(candidates);
            expect(Storage.prototype.getItem).toHaveBeenCalledWith('candidates');
        });

        it('должен возвращать пустой массив если данных нет', () => {
            expect(loadCandidates()).toEqual([]);
        });

        it('должен возвращать пустой массив при ошибке парсинга', () => {
            storage.set('candidates', 'invalid json {]');
            expect(loadCandidates()).toEqual([]);
            expect(console.log).toHaveBeenCalled();
        });

        it('должен обрабатывать null значение', () => {
            expect(loadCandidates()).toEqual([]);
        });

        it('должен обрабатывать пустую строку', () => {
            storage.set('candidates', '');
            expect(loadCandidates()).toEqual([]);
        });
    });

    describe('saveCandidates', () => {
        it('должен сохранять кандидатов в localStorage', () => {
            const candidates = [
                { id: 1, name: 'John Doe', email: 'john@example.com' },
                { id: 2, name: 'Jane Smith', email: 'jane@example.com' },
            ];
            saveCandidates(candidates);
            expect(Storage.prototype.setItem).toHaveBeenCalledWith(
                'candidates',
                JSON.stringify(candidates)
            );
            expect(storage.get('candidates')).toBe(JSON.stringify(candidates));
        });

        it('должен сохранять пустой массив', () => {
            saveCandidates([]);
            expect(Storage.prototype.setItem).toHaveBeenCalledWith('candidates', '[]');
        });

        it('должен сохранять объект кандидата', () => {
            const candidate = { id: 1, name: 'John Doe' };
            saveCandidates(candidate);
            expect(Storage.prototype.setItem).toHaveBeenCalledWith(
                'candidates',
                JSON.stringify(candidate)
            );
            expect(storage.get('candidates')).toBe(JSON.stringify(candidate));
        });
    });
});
