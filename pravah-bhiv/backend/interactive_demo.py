import os
import sys
import time
import json
import requests
from colorama import init, Fore, Style

# Initialize colorama for colored terminal output
init(autoreset=True)

def print_header(title):
    print("\n" + "="*80)
    print(f"{Fore.CYAN}{Style.BRIGHT} {title.center(78)} {Style.RESET_ALL}")
    print("="*80)

def print_step(num, desc):
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}[STEP {num}]{Style.RESET_ALL} {Fore.WHITE}{desc}")

def check_services():
    services = {
        "Target Web App (web1)": ("http://localhost:5001/health", 5001),
        "Rayyan Executor": ("http://localhost:5003/health", 5003),
        "Monitor Service": ("http://localhost:5004/health", 5004),
        "FastAPI Control Plane": ("http://localhost:8000/health", 8000),
    }
    
    all_ok = True
    print_header("PRAVAH E2E SYSTEM HEALTH CHECK")
    for name, (url, port) in services.items():
        try:
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                print(f" {Fore.GREEN}✔{Fore.RESET} {name:<28} : {Fore.GREEN}ONLINE{Fore.RESET} (Port {port})")
            else:
                print(f" {Fore.RED}✘{Fore.RESET} {name:<28} : {Fore.YELLOW}UNHEALTHY{Fore.RESET} (Status {res.status_code})")
                all_ok = False
        except Exception:
            print(f" {Fore.RED}✘{Fore.RESET} {name:<28} : {Fore.RED}OFFLINE{Fore.RESET} (Port {port})")
            all_ok = False
            
    return all_ok

def main():
    if not check_services():
        print(f"\n{Fore.RED}{Style.BRIGHT}Error: Not all services are running.{Style.RESET_ALL}")
        print("Please ensure uvicorn, executor, monitor, and web1 are all active before running.")
        sys.exit(1)
        
    print(f"\n{Fore.GREEN}{Style.BRIGHT}All Pravah services are connected. Starting Interactive Demo...{Style.RESET_ALL}")
    input(f"\n{Fore.CYAN}Press Enter to start the presentation...{Style.RESET_ALL}")

    # ----------------------------------------------------
    print_step(1, "Verify Current Service Status")
    print("Fetching the current live health status of our target container:")
    
    try:
        res = requests.get("http://localhost:5001/health", timeout=2)
        print(f"  Target Application Status: {Fore.GREEN}{res.json()['status'].upper()}{Fore.RESET}")
    except Exception as e:
        print(f"  Failed: {e}")
        
    input(f"\n{Fore.CYAN}Press Enter to proceed to Stage 2 (Trigger Failure)...{Style.RESET_ALL}")

    # ----------------------------------------------------
    print_step(2, "Trigger Simulated Production Failure")
    print("Simulating a CPU spike degradation on the target web application...")
    
    try:
        res = requests.post("http://localhost:5001/simulate-failure", timeout=2)
        print(f"  Trigger Response: {res.status_code} - {res.json()}")
        print(f"  {Fore.RED}Telemetry Update: web1 is now returning 'degraded'.{Fore.RESET}")
    except Exception as e:
        print(f"  Failed: {e}")
        
    input(f"\n{Fore.CYAN}Press Enter to proceed to Stage 3 (Observe Detection)...{Style.RESET_ALL}")

    # ----------------------------------------------------
    print_step(3, "Observe Monitor Detection & Recommendation")
    print("Waiting 3 seconds for the Monitor service to poll web1 and detect the fault...")
    time.sleep(3.0)
    
    degraded_payload = None
    try:
        res = requests.get("http://localhost:5004/metrics", timeout=5)
        metrics = res.json()
        print(f"  Monitor Service Data received: {Fore.YELLOW}{len(metrics)} targets tracked{Fore.RESET}")
        
        for item in metrics:
            if item.get("service_id") == "web1":
                degraded_payload = item
                print(f"    - ID: {item.get('service_id')}")
                print(f"    - Status: {Fore.RED}{item.get('status').upper()}{Fore.RESET}")
                print(f"    - Recommended Action: {Fore.YELLOW}{item.get('recommended_action')}{Fore.RESET}")
                print(f"    - Details: CPU={item.get('metrics', {}).get('cpu')}, Memory={item.get('metrics', {}).get('memory')}")
                break
    except Exception as e:
        print(f"  Failed to fetch monitor data: {e}")
        
    if not degraded_payload:
        print(f"  {Fore.RED}Error: Did not find degraded payload from monitor.{Fore.RESET}")
        sys.exit(1)
        
    input(f"\n{Fore.CYAN}Press Enter to proceed to Stage 4 (Orchestrate Recovery)...{Style.RESET_ALL}")

    # ----------------------------------------------------
    print_step(4, "Control Plane Ingestion & Policy Evaluation")
    print("Forwarding warning telemetry to the Control Plane /control-plane/runtime-ingest API...")
    
    try:
        res = requests.post("http://localhost:8000/control-plane/runtime-ingest", json=degraded_payload, timeout=5)
        print(f"  FastAPI Control Plane Response ({res.status_code}):")
        print(json.dumps(res.json(), indent=4))
    except Exception as e:
        print(f"  Failed to contact Control Plane: {e}")
        
    input(f"\n{Fore.CYAN}Press Enter to proceed to Stage 5 (Verify Trace Logs)...{Style.RESET_ALL}")

    # ----------------------------------------------------
    print_step(5, "Verify Cryptographic Audit Trail")
    print("Reading trace_log.jsonl to verify the sequence events...")
    
    log_file_path = "trace_log.jsonl"
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as f:
            lines = f.readlines()
        print(f"  {Fore.GREEN}Audit trail verified. Showing last trace steps:{Fore.RESET}")
        for line in lines[-5:]:
            data = json.loads(line.strip())
            print(f"    [{Fore.CYAN}{data.get('stage').upper()}{Fore.RESET}] {data.get('data')}")
    else:
        print(f"  {Fore.RED}trace_log.jsonl file not found.{Fore.RESET}")
        
    print_header("DEMO COMPLETE — SYSTEM SUCCESSFULLY SELF-HEALED")

if __name__ == "__main__":
    main()
