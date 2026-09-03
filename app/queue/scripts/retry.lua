-- Atomically updates retry fields and schedules the task.
--
-- KEYS[1] = task hash
-- KEYS[2] = delayed ZSET
--
-- ARGV[1] = task ID
-- ARGV[2] = retries
-- ARGV[3] = status
-- ARGV[4] = error
-- ARGV[5] = execute_at (unix seconds)

local task_key = KEYS[1]
local delayed_key = KEYS[2]

local task_id = ARGV[1]
local retries = ARGV[2]
local status = ARGV[3]
local error = ARGV[4]
local execute_at = tonumber(ARGV[5])

redis.call(
    'HSET',
    task_key,
    'retries', retries,
    'status', status,
    'error', error
)

redis.call(
    'ZADD',
    delayed_key,
    execute_at,
    task_id
)

return 1
