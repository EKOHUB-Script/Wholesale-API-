import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Redis URL이 환경변수에 있으면 Redis 사용, 없으면 메모리 사용 (Render 권장)
storage_uri = os.environ.get('REDIS_URL', 'memory://')

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour"],
    storage_uri=storage_uri,
    strategy="fixed-window"
)
