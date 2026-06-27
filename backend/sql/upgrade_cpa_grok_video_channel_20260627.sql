-- CPA Grok 视频渠道接入说明：
-- 1. 渠道 protocol_type 使用 openai。
-- 2. 渠道 provider_variant 使用 cpa-grok-video。
-- 3. 渠道 base_url 填 CPA 服务地址，例如 http://43.155.142.220:8317 或 http://43.155.142.220:8317/v1。
-- 4. 模型映射 actual_model_name 可配置为 grok-imagine-video 或 grok-imagine-video-1.5-preview。
-- 5. CPA Grok 视频实际最大 15 秒；用户传入超过 15 秒时系统按 15 秒生成和计费。

UPDATE `channel`
SET `provider_variant` = 'cpa-grok-video',
    `health_check_enabled` = 0
WHERE `provider_variant` = 'cpa-grok-video';
