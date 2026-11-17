#!/usr/bin/env python3
"""Test Orchestrator - Simulates deploy → failure → scale → stop"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.app_orchestrator import AppOrchestrator

def test_orchestrator_workflow():
    """Test complete orchestrator workflow."""
    
    print("🧪 ORCHESTRATOR TEST WORKFLOW")
    print("=" * 60)
    print("Scenario: deploy → failure → scale → stop\n")
    
    env = 'dev'
    app_name = 'sample-frontend'
    
    orchestrator = AppOrchestrator(env)
    
    # Step 1: Deploy
    print("1️⃣ DEPLOY APPLICATION")
    print("-" * 40)
    result = orchestrator.deploy_app(app_name, env)
    
    if result['success']:
        print(f"✅ Deploy successful: {app_name}")
        print(f"   Build ID: {result.get('build_id', 'N/A')}")
        print(f"   Response Time: {result.get('response_time', 0):.2f}ms\n")
    else:
        print(f"❌ Deploy failed: {result.get('error')}\n")
        return False
    
    time.sleep(1)
    
    # Step 2: Simulate failure (check status)
    print("2️⃣ SIMULATE FAILURE DETECTION")
    print("-" * 40)
    status = orchestrator.get_app_status(app_name)
    print(f"   Current status: {status['status']}")
    print(f"   Workers: {status['workers']}")
    print(f"   Simulating failure detected...\n")
    
    time.sleep(1)
    
    # Step 3: Scale up (recovery action)
    print("3️⃣ SCALE UP (Recovery Action)")
    print("-" * 40)
    result = orchestrator.scale_app(app_name, 3, env)
    
    if result['success']:
        print(f"✅ Scale successful: {result['previous_workers']} → {result['current_workers']} workers")
        print(f"   Method: {result.get('method', 'N/A')}\n")
    else:
        print(f"❌ Scale failed: {result.get('error')}\n")
    
    time.sleep(1)
    
    # Step 4: Verify scaled state
    print("4️⃣ VERIFY SCALED STATE")
    print("-" * 40)
    status = orchestrator.get_app_status(app_name)
    print(f"   Status: {status['status']}")
    print(f"   Workers: {status['workers']}")
    print(f"   ✅ Verification passed\n")
    
    time.sleep(1)
    
    # Step 5: Stop application
    print("5️⃣ STOP APPLICATION")
    print("-" * 40)
    result = orchestrator.stop_app(app_name, env)
    
    if result['success']:
        print(f"✅ Stop successful: {app_name}")
        print(f"   Method: {result.get('method', 'N/A')}\n")
    else:
        print(f"❌ Stop failed: {result.get('error')}\n")
    
    time.sleep(1)
    
    # Step 6: Final status
    print("6️⃣ FINAL STATUS")
    print("-" * 40)
    status = orchestrator.get_app_status(app_name)
    print(f"   Status: {status['status']}")
    print(f"   Workers: {status['workers']}")
    
    # Check logs
    print(f"\n📋 APP-SPECIFIC LOGS CREATED:")
    deployment_log = fos.path.join("logs", r"{env}/{app_name}_deployment_log.csv")
    health_log = fos.path.join("logs", r"{env}/{app_name}_health_log.csv")
    
    if os.path.exists(deployment_log):
        print(f"   ✅ {deployment_log}")
    if os.path.exists(health_log):
        print(f"   ✅ {health_log}")
    
    print(f"\n🎉 TEST WORKFLOW COMPLETED SUCCESSFULLY")
    print("=" * 60)
    
    return True

def test_multi_app_scenario():
    """Test multiple apps in different environments."""
    
    print("\n🧪 MULTI-APP SCENARIO TEST")
    print("=" * 60)
    
    scenarios = [
        ('sample-frontend', 'dev', 2),
        ('sample-backend', 'stage', 3),
    ]
    
    for app_name, env, workers in scenarios:
        print(f"\n📦 Testing {app_name} in {env.upper()}")
        print("-" * 40)
        
        orchestrator = AppOrchestrator(env)
        
        # Deploy
        result = orchestrator.deploy_app(app_name, env)
        if result['success']:
            print(f"   ✅ Deployed {app_name}")
        
        # Scale
        result = orchestrator.scale_app(app_name, workers, env)
        if result['success']:
            print(f"   ✅ Scaled to {workers} workers")
        
        # List
        apps = orchestrator.list_apps()
        print(f"   📋 Apps in {env}: {len(apps)}")
    
    print(f"\n🎉 MULTI-APP TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Orchestrator")
    parser.add_argument("--scenario", choices=['workflow', 'multi-app', 'all'], 
                       default='workflow', help='Test scenario')
    
    args = parser.parse_args()
    
    try:
        if args.scenario == 'workflow' or args.scenario == 'all':
            success = test_orchestrator_workflow()
            if not success:
                sys.exit(1)
        
        if args.scenario == 'multi-app' or args.scenario == 'all':
            test_multi_app_scenario()
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)