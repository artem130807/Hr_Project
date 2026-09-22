import {
    answersForSubmit,
    buildProfAnswerEntry,
    fillUnansweredAsTimedOut,
    markQuestionViolated,
} from './profTestTake';

describe('profTestTake', () => {
    it('buildProfAnswerEntry marks forced_incorrect from violations', () => {
        const entry = buildProfAnswerEntry({
            value: 'A',
            optionIndex: 0,
            violations: ['mouse_leave'],
        });
        expect(entry.forced_incorrect).toBe(true);
        expect(entry.option_index).toBe(0);
    });

    it('markQuestionViolated appends violation', () => {
        const next = markQuestionViolated({}, 5, 'tab_blur');
        expect(next['5'].forced_incorrect).toBe(true);
        expect(next['5'].violations).toEqual(['tab_blur']);
    });

    it('answersForSubmit keeps forced empty answers', () => {
        const answers = {
            1: buildProfAnswerEntry({ value: 'ok', optionIndex: 1 }),
            2: buildProfAnswerEntry({ forcedIncorrect: true, violations: ['tab_blur'] }),
        };
        const out = answersForSubmit(answers, [{ id: 1 }, { id: 2 }, { id: 3 }]);
        expect(out['1'].value).toBe('ok');
        expect(out['2'].forced_incorrect).toBe(true);
        expect(out['3']).toBeUndefined();
    });

    it('fillUnansweredAsTimedOut marks missing questions', () => {
        const filled = fillUnansweredAsTimedOut(
            { 1: buildProfAnswerEntry({ value: 'a', optionIndex: 0 }) },
            [{ id: 1 }, { id: 2 }]
        );
        expect(filled['1'].value).toBe('a');
        expect(filled['2'].forced_incorrect).toBe(true);
    });
});
