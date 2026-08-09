import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Render 무료 플랜(싱글 인스턴스)이므로 메모리 기반 저장소로도 충분히 방어 가능.
# (다중 인스턴스 확장 시에는 Redis 환경변수를 자동으로 사용하도록 설정)
storage_uri = os.environ.get('REDIS_URL', 'memory://')

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour"],
    storage_uri=storage_uri,
    strategy="fixed-window"
)
