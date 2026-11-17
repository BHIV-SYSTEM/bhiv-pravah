import requests
import time
import os
import json

def test_normalization_and_persistence():
    print("--- 1. Resetting persistent state ---")
    state_path = "logs/control_plane/governance_state.json"
    if os.path.exists(state_path):
        try:
            os.remove(state_path)
            print("Removed old governance state file.")
        except Exception as e:
            print(f"Could not remove governance state: {e}")
    else:
        print("No old governance state file found.")

    # Base payload for testing
    payload = {
        "service_id": "web1",
        "timestamp": "2026-06-03T15:20:55Z",
        "status": "degraded",
        "metrics": {
            "cpu": 95,
            "memory": 60,
            "error_rate": 0.0,
            "uptime": 12345
        },
        "issue_detected": True,
        "issue_type": "high_cpu",
        "recommended_action": "scale_up"
    }

    print("\n--- 2. Verifying Staging Normalization ---")
    # Set ENVIRONMENT to staging (lowercase, mixed) to verify mapping to STAGE
    os.environ["ENVIRONMENT"] = "staging"
    
    # We first verify if we can reach Control Plane
    try:
        res = requests.get("http://localhost:8000/health", timeout=3)
        print(f"Control Plane health: {res.status_code} {res.json()}")
    except Exception as e:
        print(f"Error reaching Control Plane: {e}")
        return

    # Trigger runtime ingestion under "staging" env
    # Note: Uvicorn runs in a separate process, so setting os.environ locally might not affect it unless we restarted uvicorn.
    # To test normalization inside the same python context as well, we will run both direct unit checks and API checks.
    
    print("Triggering API runtime-ingest under local process environment...")
    try:
        # We trigger uvicorn which is already running, wait, uvicorn's ENVIRONMENT is whatever it was started with (probably DEV).
        # We can test backend API ingest:
        res = requests.post("http://localhost:8000/control-plane/runtime-ingest", json=payload, timeout=5)
        print(f"Ingest response: {res.status_code}")
        print(json.dumps(res.json(), indent=2))
    except Exception as e:
        print(f"Error calling runtime-ingest: {e}")

    # Direct unit test of normalization and persistence in ActionGovernance
    print("\n--- 3. Direct Unit Checks in ActionGovernance ---")
    try:
        from control_plane.core.action_governance import ActionGovernance, normalize_environment
        
        # Test normalize_environment helper
        print(f"normalize_environment('staging') -> {normalize_environment('staging')}")
        print(f"normalize_environment('stage') -> {normalize_environment('stage')}")
        print(f"normalize_environment('PRODUCTION') -> {normalize_environment('PRODUCTION')}")
        
        # Test ActionGovernance normalized initialization
        gov_stage = ActionGovernance(env="staging")
        print(f"gov_stage.env (should be 'stage'): '{gov_stage.env}'")
        
        gov_prod = ActionGovernance(env="production")
        print(f"gov_prod.env (should be 'prod'): '{gov_prod.env}'")
        
        # Test Cooldown check (in-memory & loading check)
        gov_dev = ActionGovernance(env="dev")
        print(f"Initial dev env cooldown check for scale_up: {gov_dev._check_cooldown('scale_up', time.time()).to_dict()}")
        
        # Record an action
        print("Recording 'scale_up' action in gov_dev...")
        current_time = time.time()
        gov_dev._record_action("scale_up", current_time, {"app_name": "web1", "env": "dev"})
        
        # Verify state file was created
        if os.path.exists(state_path):
            print(f"State file created successfully at {state_path}.")
            with open(state_path, "r") as f:
                print("State JSON content:", f.read())
        else:
            print("State file was NOT created!")
            
        # Verify cooldown check is now active on the SAME instance
        cooldown_check = gov_dev._check_cooldown("scale_up", current_time + 10)
        print(f"Cooldown check +10s on same instance (should block): {cooldown_check.should_block} (Reason: {cooldown_check.reason})")
        
        # Verify cooldown check on a FRESH instance (Persistence test!)
        print("Creating a fresh ActionGovernance instance to verify state persistence load...")
        fresh_gov = ActionGovernance(env="dev")
        fresh_cooldown_check = fresh_gov._check_cooldown("scale_up", current_time + 10)
        print(f"Cooldown check +10s on fresh instance (should block): {fresh_cooldown_check.should_block} (Reason: {fresh_cooldown_check.reason})")
        
        # Verify evaluation contract blocks
        from contracts.decision_contract import validate_decision_contract
        decision = validate_decision_contract({
            "decision_type": "execution",
            "action": "scale_up",
            "parameters": {"service_id": "web1"},
            "version": "v1"
        })
        contract_check = fresh_gov.evaluate_contract(decision, {"app_name": "web1", "env": "dev"})
        print(f"evaluate_contract on fresh instance (should block): {contract_check.should_block} (Reason: {contract_check.reason})")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_normalization_and_persistence()
