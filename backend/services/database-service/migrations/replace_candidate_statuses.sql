-- Replace candidate status enum with the hiring funnel used by HR UI.
-- Safe to re-run: remaps legacy labels, recreates enum with only new values.

DO $$
DECLARE
    rel_udt text;
    appr_udt text;
BEGIN
    SELECT t.typname INTO rel_udt
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    JOIN pg_type t ON t.oid = a.atttypid
    WHERE c.relname = 'candidate_vacancy_relations' AND a.attname = 'status' AND NOT a.attisdropped
    LIMIT 1;

    SELECT t.typname INTO appr_udt
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    JOIN pg_type t ON t.oid = a.atttypid
    WHERE c.relname = 'approvals' AND a.attname = 'new_status' AND NOT a.attisdropped
    LIMIT 1;

    IF rel_udt IS NULL THEN
        RETURN;
    END IF;

    -- Widen to text so we can remap freely
    EXECUTE format(
        'ALTER TABLE candidate_vacancy_relations ALTER COLUMN status TYPE TEXT USING status::text'
    );
    IF appr_udt IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE approvals ALTER COLUMN new_status TYPE TEXT USING new_status::text'
        );
    END IF;

    -- Remap legacy → new funnel
    UPDATE candidate_vacancy_relations SET status = CASE status
        WHEN 'Отправлено приглашение в бота' THEN 'откликнулся'
        WHEN 'Перешел в бота' THEN 'откликнулся'
        WHEN 'Посмотрел подробную вакансию' THEN 'откликнулся'
        WHEN 'Посмотрел общую информацию' THEN 'откликнулся'
        WHEN 'Посмотрел информацию о корпоративной культуре' THEN 'откликнулся'
        WHEN 'Проверил своё резюме' THEN 'откликнулся'
        WHEN 'Начал тестирование' THEN 'тест: отправлен'
        WHEN 'Закончил тестирование' THEN 'тест: пройден'
        WHEN 'Записался на встречу' THEN 'собес'
        WHEN 'Прошел практическое задание' THEN 'собес'
        WHEN 'Отказ. Переведен в архив' THEN 'отказ'
        WHEN 'Отказ. В черном списке' THEN 'не подходит'
        WHEN 'Одобрен рекрутером' THEN 'собес'
        WHEN 'Одобрен руководителем' THEN 'собес'
        WHEN 'Одобрен собственником' THEN 'собес'
        WHEN 'Под вопросом у рекрутера' THEN 'откликнулся'
        WHEN 'Кандидат думает' THEN 'подумать'
        WHEN 'Наш HR созвонился' THEN 'собес'
        WHEN 'Гостевой день' THEN 'собес'
        WHEN 'Принял оффер' THEN 'ВНР'
        WHEN 'Отказался от оффера. В архиве.' THEN 'отказался'
        WHEN 'Обучение' THEN 'ВНР'
        WHEN 'Нанят' THEN 'ВНР'
        WHEN 'Кандидат отказался' THEN 'отказался'
        WHEN 'Резерв' THEN 'откликнулся'
        ELSE status
    END
    WHERE status IS NOT NULL;

    IF appr_udt IS NOT NULL THEN
        UPDATE approvals SET new_status = CASE new_status
            WHEN 'Отправлено приглашение в бота' THEN 'откликнулся'
            WHEN 'Перешел в бота' THEN 'откликнулся'
            WHEN 'Посмотрел подробную вакансию' THEN 'откликнулся'
            WHEN 'Посмотрел общую информацию' THEN 'откликнулся'
            WHEN 'Посмотрел информацию о корпоративной культуре' THEN 'откликнулся'
            WHEN 'Проверил своё резюме' THEN 'откликнулся'
            WHEN 'Начал тестирование' THEN 'тест: отправлен'
            WHEN 'Закончил тестирование' THEN 'тест: пройден'
            WHEN 'Записался на встречу' THEN 'собес'
            WHEN 'Прошел практическое задание' THEN 'собес'
            WHEN 'Отказ. Переведен в архив' THEN 'отказ'
            WHEN 'Отказ. В черном списке' THEN 'не подходит'
            WHEN 'Одобрен рекрутером' THEN 'собес'
            WHEN 'Одобрен руководителем' THEN 'собес'
            WHEN 'Одобрен собственником' THEN 'собес'
            WHEN 'Под вопросом у рекрутера' THEN 'откликнулся'
            WHEN 'Кандидат думает' THEN 'подумать'
            WHEN 'Наш HR созвонился' THEN 'собес'
            WHEN 'Гостевой день' THEN 'собес'
            WHEN 'Принял оффер' THEN 'ВНР'
            WHEN 'Отказался от оффера. В архиве.' THEN 'отказался'
            WHEN 'Обучение' THEN 'ВНР'
            WHEN 'Нанят' THEN 'ВНР'
            WHEN 'Кандидат отказался' THEN 'отказался'
            WHEN 'Резерв' THEN 'откликнулся'
            ELSE new_status
        END
        WHERE new_status IS NOT NULL;
    END IF;

    -- Drop old enum type(s) if unused, recreate canonical type
    BEGIN
        EXECUTE 'DROP TYPE IF EXISTS candidatestatus CASCADE';
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    CREATE TYPE candidatestatus AS ENUM (
        'холодный контакт',
        'не подходит',
        'отказался',
        'откликнулся',
        'тест: отправлен',
        'тест: не прошли',
        'тест: пройден',
        'собес',
        'подумать',
        'отказ',
        'оффер принят',
        'Full documents',
        'ВНР',
        'уволился'
    );

    -- Fallback unknown leftovers on the funnel column only
    UPDATE candidate_vacancy_relations
    SET status = 'откликнулся'
    WHERE status IS NOT NULL
      AND status NOT IN (
        'холодный контакт','не подходит','отказался','откликнулся',
        'тест: отправлен','тест: не прошли','тест: пройден',
        'собес','подумать','отказ','оффер принят','Full documents','ВНР','уволился'
      );

    EXECUTE 'ALTER TABLE candidate_vacancy_relations
             ALTER COLUMN status TYPE candidatestatus USING status::candidatestatus';

    -- approvals.new_status stores decision labels (not funnel enum)
END
$$;
