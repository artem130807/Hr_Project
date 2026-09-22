jest.mock('../config/api', () => ({
    API_URL: 'http://api.test',
    API_PREFIX: '/v1',
}));

jest.mock('../utils/http', () => ({
    http: {
        get: jest.fn(),
        getBlob: jest.fn(),
    },
}));

describe('analyticsApi', () => {
    beforeEach(() => {
        jest.resetModules();
        const { http } = require('../utils/http');
        http.get.mockReset();
        http.get.mockResolvedValue({});
    });

    it('getHrProfileStats calls analytics/hr-profile', async () => {
        const { http } = require('../utils/http');
        http.get.mockResolvedValue({ hired: 6, in_work: 5, interviews: 26, interviews_this_week: 5 });
        const { getHrProfileStats } = require('./analyticsApi');
        const row = await getHrProfileStats();
        expect(http.get).toHaveBeenCalledWith('/analytics/hr-profile');
        expect(row.hired).toBe(6);
        expect(row.interviews).toBe(26);
    });

    it('getHrProfileStats passes hr_user_id', async () => {
        const { http } = require('../utils/http');
        const { getHrProfileStats } = require('./analyticsApi');
        await getHrProfileStats('hr-1');
        expect(http.get).toHaveBeenCalledWith('/analytics/hr-profile?hr_user_id=hr-1');
    });
});
