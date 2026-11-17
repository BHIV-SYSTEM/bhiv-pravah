#!/usr/bin/env python3
"""
Redis Setup Guide for Production
================================

For production deployment, install and configure Redis server:

Windows:
--------
1. Download Redis from: https://github.com/microsoftarchive/redis/releases
2. Install and start Redis service
3. Verify: redis-cli ping (should return PONG)

Linux/macOS:
-----------
sudo apt-get install redis-server  # Ubuntu/Debian
brew install redis                  # macOS
redis-server                        # Start server

Docker:
-------
docker run -d -p 6379:6379 redis:7-alpine

Configuration:
--------------
Update environments/*.env files:
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

Verification:
-------------
python -c "import redis; r=redis.Redis(); print(r.ping())"
"""

if __name__ == "__main__":
    print(__doc__)