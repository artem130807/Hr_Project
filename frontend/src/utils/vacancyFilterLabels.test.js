import {
    WORK_FORMAT_OPTIONS,
    EXPERIENCE_OPTIONS,
    labelWorkFormat,
    labelExperience,
    formatFilterSummary,
    formatFilterTitle,
    validateFilterForm,
    filterToForm,
} from './vacancyFilterLabels';

describe('vacancyFilterLabels', () => {
    it('exposes work format options for the form', () => {
        const values = WORK_FORMAT_OPTIONS.map((o) => o.value);
        expect(values).toEqual(
            expect.arrayContaining(['remote', 'office', 'hybrid', 'field', 'shift'])
        );
    });

    it('exposes experience options aligned with backend enum', () => {
        const values = EXPERIENCE_OPTIONS.map((o) => o.value);
        expect(values).toEqual(
            expect.arrayContaining([
                'noExperience',
                'between1And3',
                'between3And6',
                'moreThan6',
            ])
        );
    });

    it('labels work format and experience in Russian', () => {
        expect(labelWorkFormat('remote')).toMatch(/удал/i);
        expect(labelWorkFormat('field')).toMatch(/разъезд/i);
        expect(labelExperience('noExperience')).toMatch(/нет|без/i);
        expect(labelExperience('between1And3')).toMatch(/1/);
    });

    it('formatFilterSummary lists filled fields only', () => {
        const text = formatFilterSummary({
            city: 'Москва',
            age_from: 25,
            age_to: 40,
            experience: 'between1And3',
            work_format: 'remote',
        });
        expect(text).toContain('Москва');
        expect(text).toContain('25');
        expect(text).toContain('40');
        expect(text).toMatch(/удал/i);
        expect(text).toMatch(/отказ/i);
    });

    it('formatFilterSummary handles empty filter', () => {
        expect(formatFilterSummary({})).toMatch(/пуст|не задан/i);
    });

    it('formatFilterTitle prefers city', () => {
        expect(formatFilterTitle({ id: 4, city: 'СПб' })).toContain('СПб');
        expect(formatFilterTitle({ id: 4 })).toContain('#4');
    });

    it('validateFilterForm rejects inverted age range', () => {
        const errors = validateFilterForm({ age_from: 40, age_to: 20 });
        expect(errors.age).toBeTruthy();
    });

    it('validateFilterForm allows a single criterion', () => {
        expect(validateFilterForm({ city: 'Казань' })).toEqual({});
    });

    it('validateFilterForm requires at least one criterion', () => {
        expect(validateFilterForm({}).criteria).toBeTruthy();
        expect(validateFilterForm({ action: 'consider' }).criteria).toBeTruthy();
    });

    it('filterToForm maps API filter to form fields', () => {
        expect(
            filterToForm({
                city: 'Москва',
                age_from: 25,
                age_to: 40,
                experience: 'between1And3',
                work_format: 'remote',
            })
        ).toEqual({
            city: 'Москва',
            age_from: '25',
            age_to: '40',
            experience: 'between1And3',
            work_format: 'remote',
            action: 'discard',
        });
        expect(filterToForm(null).city).toBe('');
        expect(filterToForm(null).action).toBe('discard');
    });
});
