-- 停用已失效的 zz.211b Grok 视频映射。
-- 仅影响两个视频模型，不禁用渠道，也不影响该渠道的文本模型映射。

UPDATE `model_channel_mapping` m
JOIN `unified_model` um ON um.`id` = m.`unified_model_id`
JOIN `channel` ch ON ch.`id` = m.`channel_id`
SET m.`enabled` = 0
WHERE ch.`name` = 'zz.211b'
  AND LOWER(TRIM(TRAILING '/' FROM TRIM(ch.`base_url`))) IN (
    'https://zz.211b.site',
    'https://zz.211b.site/v1'
  )
  AND um.`model_name` IN ('grok-video', 'grok-imagine-video-1.5-preview');
