#!/bin/bash
# Start the sandbox Redis instance (userspace build).
mkdir -p /home/z/infra/redis-data
exec /home/z/infra/redis-7.2.5/src/redis-server \
  --port 6379 \
  --daemonize no \
  --dir /home/z/infra/redis-data \
  --save "" \
  --appendonly no \
  --protected-mode yes \
  --bind 127.0.0.1
