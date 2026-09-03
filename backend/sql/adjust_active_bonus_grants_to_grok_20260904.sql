-- 将当前生效中的赠送批次统一限制为 Grok 系列。
-- 已取消/已过期批次保留历史配置不变；重复执行不会产生额外变化。
UPDATE subscription_bonus_grant
SET model_series = '["grok"]'
WHERE status = 'active'
  AND (model_series IS NULL OR TRIM(model_series) <> '["grok"]');
