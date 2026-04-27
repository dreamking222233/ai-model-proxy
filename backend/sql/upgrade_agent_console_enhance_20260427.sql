-- 代理端后台增强数据修复
-- 用途：回填历史套餐记录的 agent_id，确保代理端“套餐管理 -> 发放记录”可以看到历史记录。

UPDATE user_subscription us
JOIN sys_user u ON u.id = us.user_id
SET us.agent_id = u.agent_id
WHERE us.agent_id IS NULL
  AND u.agent_id IS NOT NULL;

