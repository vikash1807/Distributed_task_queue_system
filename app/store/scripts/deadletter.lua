-- Atomically marks a task failed and pushes its 
-- FailedTask JSON onto the dead-letter queue.
--
-- KEYS[1] = task hash
-- KEYS[2] = dead-letter LIST
--
-- ARGV[1] = status
-- ARGV[2] = failed task JSON

local task_key = KEYS[1]
local deadletter_key = KEYS[2]

local status = ARGV[1]
local failed_task_json = ARGV[2]

redis.call(
    'HSET',
    task_key,
    'status',
    status
)

redis.call(
    'LPUSH',
    deadletter_key,
    failed_task_json
)

return 1