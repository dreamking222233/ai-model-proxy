-- Convert historical shared API values into dynamic inheritance semantics.
-- This is idempotent and preserves every agent that has an independent API domain.

UPDATE `agent` AS a
JOIN `system_config` AS sc
  ON sc.`config_key` = 'api_base_url'
SET a.`quickstart_api_base_url` = NULL
   , a.`api_domain` = NULL
WHERE NULLIF(TRIM(a.`api_domain`), '') IS NULL
  AND (
      NULLIF(TRIM(a.`quickstart_api_base_url`), '') IS NULL
      OR LOWER(TRIM(TRAILING '/' FROM TRIM(a.`quickstart_api_base_url`))) IN (
          LOWER(TRIM(TRAILING '/' FROM TRIM(sc.`config_value`))),
          'https://api.xiaoleai.team',
          'http://api.xiaoleai.team'
      )
  );

SELECT ROW_COUNT() AS `agent_shared_api_values_cleared`;

SELECT COUNT(*) AS `agent_shared_api_inherited_count`
FROM `agent`
WHERE `api_domain` IS NULL
  AND (`quickstart_api_base_url` IS NULL OR TRIM(`quickstart_api_base_url`) = '');
