-- Split DeepSeek and Chinese domestic models out of `other`.
-- Idempotent: already-classified rows are skipped.

UPDATE unified_model
SET model_series = 'deepseek'
WHERE LOWER(model_name) LIKE 'deepseek%'
  AND model_series <> 'deepseek';

UPDATE unified_model
SET model_series = 'domestic'
WHERE model_series NOT IN ('gpt', 'claude', 'grok', 'gemini', 'deepseek', 'domestic')
  AND (
    LOWER(model_name) LIKE 'glm%'
    OR LOWER(model_name) LIKE 'chatglm%'
    OR LOWER(model_name) LIKE 'qwen%'
    OR LOWER(model_name) LIKE 'qwq%'
    OR LOWER(model_name) LIKE 'doubao%'
    OR LOWER(model_name) LIKE 'moonshot%'
    OR LOWER(model_name) LIKE 'kimi%'
    OR LOWER(model_name) LIKE 'hunyuan%'
    OR LOWER(model_name) LIKE 'ernie%'
    OR LOWER(model_name) LIKE 'spark%'
    OR LOWER(model_name) LIKE 'minimax%'
    OR LOWER(model_name) LIKE 'baichuan%'
    OR LOWER(model_name) LIKE 'internlm%'
    OR LOWER(model_name) LIKE 'yi-%'
  );

-- Historical 国模 multipliers lived on `other` because that was the CN bucket.
-- Move them onto `domestic` so GLM/Kimi/Qwen keep current rates while DeepSeek
-- can be priced independently.
UPDATE model_price_adjustment_rule
SET model_series = 'domestic'
WHERE model_series = 'other';

UPDATE user_price_adjustment_rule
SET model_series = 'domestic'
WHERE model_series = 'other';
