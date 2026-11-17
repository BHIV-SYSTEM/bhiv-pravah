#!/usr/bin/env python3
"""Environment validation script."""

import sys
from core.env_validator import validate_env

def main():
    """Validate environment configuration."""
    if len(sys.argv) != 2:
        print("Usage: python validate_env.py <env_name>")
        print("Example: python validate_env.py dev")
        sys.exit(1)
    
    env_name = sys.argv[1]
    
    try:
        validate_env(env_name)
        print(f"🎉 Environment '{env_name}' is ready to use!")
    except EnvironmentError as e:
        print(str(e))
        print(f"\n💡 Fix the issues above and run: python validate_env.py {env_name}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()