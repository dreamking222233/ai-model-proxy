-- Grok Imagine 定价调整：
-- 图片 1K=0.5 积分/张，2K=1 积分/张
-- 视频 480p/720p=0.5 积分/秒，1080p=1 积分/秒

UPDATE `unified_model`
SET
    `image_credit_multiplier` = 0.500,
    `description` = CASE `model_name`
        WHEN 'grok-imagine-image' THEN 'Grok Imagine 图片 1.0：1K 每张 0.5 媒体积分，2K 每张 1 媒体积分'
        WHEN 'grok-imagine-image-2.0' THEN 'Grok Imagine 图片 2.0：1K 每张 0.5 媒体积分，2K 每张 1 媒体积分'
        WHEN 'grok-imagine-video' THEN 'Grok Imagine 视频 1.0：480p/720p 每秒 0.5 媒体积分，最长 15 秒，参考生最长 10 秒'
        WHEN 'grok-imagine-video-1.5' THEN 'Grok Imagine 视频 1.5：480p/720p 每秒 0.5 媒体积分，1080p 每秒 1 媒体积分'
        ELSE `description`
    END
WHERE `model_name` IN (
    'grok-imagine-image',
    'grok-imagine-image-2.0',
    'grok-imagine-video',
    'grok-imagine-video-1.5'
);

UPDATE `model_image_resolution_rule` r
JOIN `unified_model` um ON um.id = r.unified_model_id
SET r.credit_cost = CASE r.resolution_code
    WHEN '1K' THEN 0.500
    WHEN '2K' THEN 1.000
    ELSE r.credit_cost
END
WHERE um.model_name IN ('grok-imagine-image', 'grok-imagine-image-2.0');
