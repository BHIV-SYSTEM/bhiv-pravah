import argparse
import os
import csv
import datetime
import sys

# CRITICAL: Prevent this simulation script from running on Render
# This file is ONLY for local CI/CD simulations, NOT for production deployment
if os.getenv('RENDER') == 'true' or os.getenv('SKIP_SIMULATIONS') == 'true':
    print("⚠️  Skipping CI/CD simulation (production/Render environment detected)")
    print("✅ Use wsgi.py for Flask API server")
    sys.exit(0)
else:
    # Only import if NOT on Render
    from agents.deploy_agent import DeployAgent
    from agents.issue_detector import IssueDetector
    from agents.uptime_monitor import UptimeMonitor
    from agents.auto_heal_agent import AutoHealAgent
    from rl.rl_trainer import RLTrainer
    from utils import simulate_data_change, trigger_dashboard_deployment
    from feedback.feedback_handler import get_user_feedback_from_terminal, log_user_feedback
    from config import THRESHOLDS
    from core.env_config import EnvironmentConfig
    from core.mcp_bridge import mcp_bridge
    from core.mcp_manager import MCPManager
    from core.mcp_adapter import MCPAdapter

# --- Main Simulation Loop ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CI/CD Simulation with Modular Agents")
    parser.add_argument("--dataset", type=str, default="dataset/student.csv")
    parser.add_argument("--fail-type", type=str, choices=['crash', 'latency'])
    parser.add_argument("--force-anomaly", action="store_true")
    parser.add_argument("--planner", type=str, choices=['random', 'rl'], default='random')
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--env", type=str, choices=['dev', 'stage', 'prod'], default='dev', help='Environment to deploy to')
    parser.add_argument("--workers", type=int, default=1, help='Number of deploy workers')
    parser.add_argument("--worker-id", type=int, default=1, help='Worker ID for this instance')
    args = parser.parse_args()

    # --- Environment Validation ---
    try:
        from core.env_validator import validate_env
        validate_env(args.env)
    except EnvironmentError as e:
        print(str(e))
        print(f"\n💡 Fix issues and run: python validate_env.py {args.env}")
        exit(1)
    except ImportError:
        # Fallback validation
        env_file = os.path.join("environments", f"{args.env}.env")
        if not os.path.exists(env_file):
            print(f"❌ Environment file missing: {env_file}")
            print(f"💡 Run: python validate_env.py {args.env}")
            exit(1)
    
    # --- Environment Configuration ---
    env_config = EnvironmentConfig(args.env)
    print(f"Running in {args.env.upper()} environment")
    
    # --- File Path Definitions ---
    DEPLOYMENT_LOG_FILE = env_config.get_log_path("deployment_log.csv")
    UPTIME_LOG_FILE = env_config.get_log_path("uptime_log.csv")
    HEALING_LOG_FILE = env_config.get_log_path("healing_log.csv")
    RL_LOG_FILE = env_config.get_log_path("rl_log.csv")
    PERFORMANCE_LOG_FILE = env_config.get_log_path("rl_performance_log.csv")
    ISSUE_LOG_FILE = env_config.get_log_path("issue_log.csv")
    USER_FEEDBACK_LOG_FILE = env_config.get_log_path("user_feedback_log.csv")

    # --- Agent Initialization ---
    print("Initializing MCP Integration...")
    # Initialize Ritesh's MCP Manager
    mcp_manager = MCPManager("mcp_messages.json")
    mcp_adapter = MCPAdapter(mcp_manager)
    print("MCP Manager integrated with sovereign bus")
    
    deploy_agent = DeployAgent(log_file=DEPLOYMENT_LOG_FILE, env=args.env, worker_id=args.worker_id)

    # Initialize IssueDetector with environment
    issue_detector = IssueDetector(
        log_file=DEPLOYMENT_LOG_FILE, 
        data_file=args.dataset, 
        issue_log_file=ISSUE_LOG_FILE,
        config=env_config.config,
        env=args.env
    )
    
    uptime_monitor = UptimeMonitor(timeline_file=UPTIME_LOG_FILE)
    
    planner = AutoHealAgent(healing_log_file=HEALING_LOG_FILE, env=args.env)
    rl_trainer = None
    if args.planner == 'rl':
        rl_trainer = RLTrainer(rl_log_file=RL_LOG_FILE, performance_log_file=PERFORMANCE_LOG_FILE, train_mode=args.train)
        print("\n--- Using RL Trainer for action selection ---")
    else:
        print("\n--- Using Random Auto-Heal Agent ---")

    # 1. Simulate a data change
    simulate_data_change(args.dataset, force_anomaly=args.force_anomaly, env=args.env)
    
    # 2. Check for data anomalies BEFORE deployment
    failure_state, reason = issue_detector.detect_failure_type()
    
    # 3. Trigger initial deployment
    should_fail = args.fail_type is not None
    status, time_ms = trigger_dashboard_deployment(should_fail=should_fail, failure_type=args.fail_type)
    deploy_agent.log_deployment(args.dataset, status, time_ms)

    # 4. If no data anomaly detected, check deployment issues
    if failure_state == "no_failure":
        failure_state, reason = issue_detector.detect_failure_type()
    
    if failure_state != "no_failure":
        system_status = uptime_monitor.last_status
        full_state = f"{failure_state}_{system_status}"
        
        uptime_monitor.update_status("DOWN", reason)
        
        if rl_trainer:
            chosen_action = rl_trainer.choose_action(failure_state)
            heal_status, heal_time, heal_type, _ = planner.execute_action(chosen_action, args.dataset)
            
            # Learn from result
            base_reward = 1 if heal_status == 'success' else -1
            user_feedback = get_user_feedback_from_terminal(failure_state, chosen_action, heal_status)
            log_user_feedback(USER_FEEDBACK_LOG_FILE, failure_state, chosen_action, heal_status, user_feedback)
            
            rl_trainer.learn(failure_state, chosen_action, base_reward, user_feedback)
        else:
            heal_status, heal_time, heal_type, chosen_action = planner.attempt_healing(failure_state, args.dataset)
        
        deploy_agent.log_deployment(args.dataset, heal_status, heal_time, action_type=heal_type)

        if heal_status == 'success':
            uptime_monitor.update_status("UP", f"Recovery successful via {heal_type}")
        else:
            print("\n--- Healing attempt failed. The service remains down. ---")
    else:
        uptime_monitor.update_status("UP", "Successful deployment")

    if rl_trainer:
        rl_trainer.save_q_table()
        if args.train:
            rl_trainer.show_learning_progress()
    
    # Process any pending MCP messages
    mcp_bridge.process_mcp_inbox()
    mcp_adapter.process_mcp_messages()
        
    print("\nCI/CD simulation finished.")

