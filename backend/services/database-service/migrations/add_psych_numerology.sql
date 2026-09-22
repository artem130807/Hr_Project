-- Additive columns for psych numerology (ЧС / ЧМ) from birth date.
ALTER TABLE psych_test_results ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE psych_test_results ADD COLUMN IF NOT EXISTS chs INTEGER;
ALTER TABLE psych_test_results ADD COLUMN IF NOT EXISTS chm INTEGER;
