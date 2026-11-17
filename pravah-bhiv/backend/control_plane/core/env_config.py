import os


def _parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

class EnvironmentConfig:
    """Loads environment-specific configuration."""
    
    def __init__(self, env=None):
        raw_env = (env or os.getenv('ENVIRONMENT', 'dev')).strip().lower()
        if raw_env in ('production', 'prod'):
            self.env = 'prod'
        elif raw_env in ('staging', 'stage'):
            self.env = 'stage'
        elif raw_env in ('development', 'dev'):
            self.env = 'dev'
        else:
            self.env = raw_env

        self.config = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment file."""
        candidates = [
            os.path.join("environments", f"{self.env}.env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "environments", f"{self.env}.env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "environments", f"{self.env}.env"),
            os.path.join(os.path.abspath(os.sep), "app", "environments", f"{self.env}.env"),
        ]
        loaded = False
        for env_file in candidates:
            if os.path.exists(env_file):
                self._load_env_file(env_file)
                loaded = True
                break

        if not loaded:
            self._populate_config_from_environ()
    
    def _populate_config_from_environ(self):
        """Populate configuration from process environment variables."""
        self.config = {
            'environment': os.getenv('ENVIRONMENT', self.env),
            'debug': os.getenv('DEBUG', 'false').lower() == 'true',
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'db_host': os.getenv('DB_HOST', '127.0.0.1'),
            'db_port': int(os.getenv('DB_PORT', 5432)),
            'redis_host': os.getenv('REDIS_HOST', 'redis'),
            'redis_port': int(os.getenv('REDIS_PORT', 6379)),
            'redis_db': int(os.getenv('REDIS_DB', 2 if self.env == 'prod' else 0)),
            'deployment_timeout': int(os.getenv('DEPLOYMENT_TIMEOUT', 30)),
            'retry_count': int(os.getenv('RETRY_COUNT', 3)),
            'latency_ms': int(os.getenv('LATENCY_THRESHOLD_MS', 16000)),
            'low_score_avg': int(os.getenv('LOW_SCORE_THRESHOLD', 40)),
            'high_heart_rate': int(os.getenv('HIGH_HEART_RATE', 120)),
            'low_oxygen_level': int(os.getenv('LOW_OXYGEN_LEVEL', 95)),
            'dashboard_port': int(os.getenv('DASHBOARD_PORT', 8501)),
            'autonomy_decisions_enabled': _parse_bool(
                os.getenv('AUTONOMY_DECISIONS_ENABLED'),
                default=True
            ),
            'autonomy_learning_enabled': _parse_bool(
                os.getenv('AUTONOMY_LEARNING_ENABLED'),
                default=self.env == 'dev'
            ),
            'emergency_freeze_enabled': _parse_bool(
                os.getenv('EMERGENCY_FREEZE_ENABLED'),
                default=False
            ),
            'emergency_freeze_reason': os.getenv(
                'EMERGENCY_FREEZE_REASON',
                ''
            )
        }

    def _load_env_file(self, env_file):
        """Simple .env file parser."""
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('export '):
                    line = line[7:].strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                
                # Handle inline comments
                if ' #' in line:
                    line = line.split(' #', 1)[0].strip()
                    
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Prevent Errno 22 on invalid keys (empty, spaces, etc.)
                import re
                if not key or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                    continue

                if key not in os.environ:
                    os.environ[key] = value
            
        self._populate_config_from_environ()
    
    def get(self, key, default=None):
        """Get configuration value with os.environ precedence."""
        env_key = key.upper()
        if env_key in os.environ:
            val = os.environ[env_key]
            expected_type = type(self.config.get(key)) if key in self.config else (type(default) if default is not None else None)
            if expected_type is bool or isinstance(default, bool):
                return _parse_bool(val, default if isinstance(default, bool) else False)
            if expected_type is int or isinstance(default, int):
                try:
                    return int(val)
                except ValueError:
                    return default
            return val
        return self.config.get(key, default)
    
    def get_log_path(self, filename):
        """Get environment-specific log path."""
        log_dir = os.path.join("logs", f"{self.env}")
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, filename)