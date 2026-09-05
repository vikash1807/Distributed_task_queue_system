-- Atomically adds a task to the ready queue and rings the doorbell.
--
-- KEYS[1] = ready ZSET
-- KEYS[2] = ready signal LIST
--
-- ARGV[1] = task ID
-- ARGV[2] = priority
-- ARGV[3] = signal cap

local ready_key = KEYS[1]
local signal_key = KEYS[2]

local task_id = ARGV[1]
local priority = tonumber(ARGV[2])
local signal_cap = tonumber(ARGV[3])

redis.call('ZADD', ready_key, -priority, task_id)

if redis.call('LLEN', signal_key) < signal_cap then
    redis.call('RPUSH', signal_key, '1')
end

return 1