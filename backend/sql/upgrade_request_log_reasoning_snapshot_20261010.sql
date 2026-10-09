-- MySQL 8: add only a nullable trailing column without copying the request log.
-- Fail quickly on a busy metadata lock. Apply before deploying the new ORM.
SET SESSION lock_wait_timeout = 5;
SET @reasoning_snapshot_sql = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log'
            AND column_name = 'reasoning_snapshot'),
    'SELECT 1',
    'ALTER TABLE request_log ADD COLUMN reasoning_snapshot TEXT NULL COMMENT ''Validated reasoning effort/mode/budget snapshot'', ALGORITHM=INSTANT'
);
PREPARE reasoning_snapshot_stmt FROM @reasoning_snapshot_sql;
EXECUTE reasoning_snapshot_stmt;
DEALLOCATE PREPARE reasoning_snapshot_stmt;
