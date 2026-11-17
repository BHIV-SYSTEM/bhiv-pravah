#!/usr/bin/env python3
"""
Multi-Environment Deployment Script
Usage: python deploy.py --env dev|stage|prod [other options]
"""

import argparse
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description="Deploy to specific environment")
    parser.add_argument("--env", type=str, choices=['dev', 'stage', 'prod'], 
                       required=True, help='Target environment')
    parser.add_argument("--dataset", type=str, default="dataset/student.csv")
    parser.add_argument("--planner", type=str, choices=['random', 'rl'], default='rl')
    parser.add_argument("--force-anomaly", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help='Number of deploy workers')
    
    args = parser.parse_args()
    
    # Validate environment first
    try:
        from core.env_validator import validate_env
        validate_env(args.env)
    except EnvironmentError as e:
        print(str(e))
        print(f"\n💡 Fix issues and run: python validate_env.py {args.env}")
        return 1
    except ImportError:
        import os
        env_file = fos.path.join("environments", r"{args.env}.env")
        if not os.path.exists(env_file):
            print(f"❌ Environment file missing: {env_file}")
            print(f"💡 Run: python validate_env.py {args.env}")
            return 1
    
    print(f"🚀 Deploying to {args.env.upper()} environment...")
    
    # Build command
    cmd = [
        sys.executable, "main.py",
        "--env", args.env,
        "--dataset", args.dataset,
        "--planner", args.planner
    ]
    
    if args.force_anomaly:
        cmd.append("--force-anomaly")
    if args.train:
        cmd.append("--train")
    if args.workers > 1:
        cmd.extend(["--workers", str(args.workers)])
    
    # Execute deployment
    try:
        result = subprocess.run(cmd, check=True)
        print(f"✅ Successfully deployed to {args.env.upper()}")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment to {args.env.upper()} failed: {e}")
        return e.returncode

if __name__ == "__main__":
    sys.exit(main())