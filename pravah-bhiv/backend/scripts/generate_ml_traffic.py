import time
import random
import sys
import os

# Add backend directory to sys path so it can find control_plane
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control_plane.core.metrics_collector import get_metrics_collector

def run_synthetic_traffic():
    print("Starting synthetic traffic generator for ML Feature Extractor...")
    print("Press Ctrl+C to stop.")
    
    # We will write to the 'prod' metrics to match your API endpoint configuration
    metrics = get_metrics_collector("prod")
    
    components = ["web_frontend", "master_db", "trade_bot", "prompt_runner"]
    
    try:
        while True:
            # 1. Generate normal latency traffic
            for comp in components:
                # Normal latency between 20ms and 150ms
                latency = random.uniform(20.0, 150.0)
                metrics.record_latency_metric(comp, "process_request", latency)
                
            # 2. Inject an anomaly (10% chance)
            if random.random() < 0.10:
                print("Injecting simulated anomaly (High Latency + Error)...")
                # High latency spike
                metrics.record_latency_metric("master_db", "process_request", random.uniform(800.0, 2000.0))
                # Generate an error
                metrics.record_error_metric("master_db", "ConnectionTimeout", 1, severity="high")
                
            # 3. Simulate Queue Depth changes
            queue_depth = int(random.gauss(50, 15))
            metrics.record_queue_metric("main_task_queue", max(0, queue_depth))
            
            # 4. Simulate Deployment success occasionally
            if random.random() < 0.05:
                metrics.record_deploy_success_rate(1, 1, 0, 450.0)
                
            print(".", end="", flush=True)
            time.sleep(0.5)  # 2 requests per second
            
    except KeyboardInterrupt:
        print("\nStopped synthetic traffic generator.")

if __name__ == "__main__":
    run_synthetic_traffic()
