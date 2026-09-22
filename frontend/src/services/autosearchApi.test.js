jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        post: jest.fn(),
        patch: jest.fn(),
    },
}));

describe('autosearchApi via DB /v1/hh proxy', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.post.mockReset();
        http.patch.mockReset();
    });

    it('getAvailableVacancies hits /hh/autosearch/vacancies/available', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue([]);
        const { getAvailableVacancies } = require('./autosearchApi');
        await getAvailableVacancies();
        expect(http.get).toHaveBeenCalledWith('/hh/autosearch/vacancies/available');
    });

    it('activateAutosearch posts vacancy id on /hh/autosearch', async () => {
        const { http } = require('../utils/http');
        http.post.mockResolvedValue({ active: true });
        const { activateAutosearch } = require('./autosearchApi');
        await activateAutosearch(42);
        expect(http.post).toHaveBeenCalledWith('/hh/autosearch/42/activate');
    });
});
