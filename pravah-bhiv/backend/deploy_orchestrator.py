#!/usr/bin/env python3
"""
Orchestrator-based Deployment Script (Thin Wrapper)
Usage: python deploy_orchestrator.py --env dev|stage|prod --app app_name [options]
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.app_orchestrator import AppOrchestrator

def main():
    parser = argparse.ArgumentParser(description="Deploy application using orchestrator")
    parser.add_argument("--env", type=str, choices=['dev', 'stage', 'prod'], 
                       required=True, help='Target environment')
    parser.add_argument("--app", type=str, required=True, help='Application name')
    parser.add_argument("--action", type=str, choices=['deploy', 'stop', 'scale'], 
                       default='deploy', help='Action to perform')
    parser.add_argument("--workers", type=int, default=1, help='Number of workers (for scale)')
    
    args = parser.parse_args()
    
    print(f"🚀 {args.action.upper()} {args.app} in {args.env.upper()} environment...")
    
    orchestrator = AppOrchestrator(args.env)
    
    try:
        if args.action == 'deploy':
            result = orchestrator.deploy_app(args.app, args.env)
        elif args.action == 'stop':
            result = orchestrator.stop_app(args.app, args.env)
        elif args.action == 'scale':
            result = orchestrator.scale_app(args.app, args.workers, args.env)
        else:
            print(f"❌ Unknown action: {args.action}")
            return 1
        
        if result['success']:
            print(f"✅ Successfully {args.action}ed {args.app} in {args.env.upper()}")
            return 0
        else:
            print(f"❌ {args.action.capitalize()} failed: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())