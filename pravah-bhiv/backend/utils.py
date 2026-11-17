import pandas as pd
import random
import time
import subprocess
import os
import shutil
from core.stage_determinism import StageDeterminismLock, log_determinism_status

def validate_environment(env_name):
    """Quick environment validation."""
    env_file = os.path.join("environments", f"{env_name}.env")
    if not os.path.exists(env_file):
        print(f"❌ Environment file missing: {env_file}")
        print(f"💡 Run: python validate_env.py {env_name}")
        return False
    return True

def simulate_data_change(dataset_path, force_anomaly=False, env='dev'):
    """Creates backup and appends new data."""
    if not os.path.exists(dataset_path):
        return
    
    shutil.copyfile(dataset_path, f"{dataset_path}.bak")
    df = pd.read_csv(dataset_path)
    
    if "student_scores" in dataset_path:
        if force_anomaly:
            # Add low scores to trigger anomaly
            for _ in range(3):
                # Stage environment: Use deterministic names and scores
                if StageDeterminismLock.is_stage_env(env):
                    names = ['Alice', 'Bob', 'Charlie']
                    subjects = ['Math', 'Science']
                    name = StageDeterminismLock.deterministic_choice(names, f"name_{_}")
                    subject = StageDeterminismLock.deterministic_choice(subjects, f"subject_{_}")
                    score = 15  # Fixed low score for anomaly
                else:
                    name = random.choice(['Alice', 'Bob', 'Charlie'])
                    subject = random.choice(['Math', 'Science'])
                    score = random.randint(10, 20)
                
                new_row = {
                    'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d'),
                    'name': name,
                    'subject': subject,
                    'score': score
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            # Stage environment: Use deterministic values
            if StageDeterminismLock.is_stage_env(env):
                names = ['Alice', 'Bob', 'Charlie']
                subjects = ['Math', 'Science']
                name = StageDeterminismLock.deterministic_choice(names, "normal_name")
                subject = StageDeterminismLock.deterministic_choice(subjects, "normal_subject")
                score = 85  # Fixed good score
            else:
                name = random.choice(['Alice', 'Bob', 'Charlie'])
                subject = random.choice(['Math', 'Science'])
                score = random.randint(70, 100)
            
            new_row = {
                'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d'),
                'name': name,
                'subject': subject,
                'score': score
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    
    df.to_csv(dataset_path, index=False)


def trigger_dashboard_deployment(timeout=15, should_fail=False, failure_type=None, env='dev'):
    """Simulates dashboard deployment health check for backend agents."""
    # Stage environment: Fixed timing for predictable demo behavior
    if StageDeterminismLock.is_stage_env(env):
        fixed_time = StageDeterminismLock.get_fixed_timing(1200) / 1000  # Convert to seconds
        time.sleep(fixed_time)
        log_determinism_status(env, "Dashboard deployment timing")
        return "success", StageDeterminismLock.get_fixed_timing(1200)  # Always succeed with fixed timing
    
    # Original behavior for dev/prod
    if should_fail and failure_type == 'crash':
        time.sleep(1.5)
        return "failure", 2000
    elif should_fail and failure_type == 'latency':
        time.sleep(timeout + 5)
        return "success", (timeout + 5) * 1000
    
    start_time = time.time()
    ui_removed = not os.path.exists(os.path.join("ui", "dashboards"))

    if ui_removed:
        time.sleep(0.5)
        return "success", (time.time() - start_time) * 1000

    try:
        process = subprocess.Popen(
            ["streamlit", "run", "ui/dashboards/dashboard.py", "--server.runOnSave", "false"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(timeout)
        status = "success" if process.poll() is None else "failure"
        if process.poll() is None:
            process.terminate()
    except Exception:
        status = "failure"
    
    return status, (time.time() - start_time) * 1000

