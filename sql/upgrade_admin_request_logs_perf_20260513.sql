ALTER TABLE `request_log`
  ADD INDEX `idx_request_log_agent_id_id` (`agent_id`, `id`),
  ADD INDEX `idx_request_log_user_id_id` (`user_id`, `id`),
  ADD INDEX `idx_request_log_requested_model_id` (`requested_model`, `id`),
  ADD INDEX `idx_request_log_status_id` (`status`, `id`),
  ADD INDEX `idx_request_log_created_at_id` (`created_at`, `id`);
