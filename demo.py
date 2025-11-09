#!/usr/bin/env python3
"""Complete demo of QueueCTL functionality"""
import subprocess
import json
import time
import os

def run_cmd(cmd, description=""):
    """Run command and display output"""
    if description:
        print(f"\n{'='*60}")
        print(f">>> {description}")
        print('='*60)
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, text=True)
    time.sleep(1)
    return result.returncode == 0

def enqueue(job_dict, description=""):
    """Enqueue a job"""
    if description:
        print(f"\n>>> {description}")
    cmd = ['queuectl', 'enqueue', json.dumps(job_dict)]
    print(f"$ queuectl enqueue '{json.dumps(job_dict)}'")
    subprocess.run(cmd)
    time.sleep(0.5)

print("""
╔════════════════════════════════════════════════════════════╗
║           QueueCTL - Complete Feature Demo                ║
║     Background Job Queue with Retry & DLQ Support         ║
╚════════════════════════════════════════════════════════════╝
""")

# Clean slate
print("\n[1] Cleaning up previous data...")
for f in ["queuectl.db", "queuectl_config.json", "queuectl_workers.pid"]:
    if os.path.exists(f):
        os.remove(f)
        print(f"  Removed {f}")

# Enqueue various jobs
run_cmd("", "[2] Enqueuing Test Jobs")
enqueue({"id": "job1", "command": "echo Job 1: Success!"}, "Simple echo job")
enqueue({"id": "job2", "command": "python -c \"print('Job 2: Python works!')\""}, "Python job")
enqueue({"id": "job3", "command": "timeout 2 >nul" if os.name == 'nt' else "sleep 2"}, "Sleep job (2 seconds)")
enqueue({"id": "job_retry", "command": "exit 1", "max_retries": 2}, "Failing job (will retry)")
enqueue({"id": "job4", "command": "echo Job 4: Another success!"}, "Another simple job")

# Check initial status
run_cmd("queuectl status", "[3] Initial Queue Status")

# List pending jobs
run_cmd("queuectl list --state pending", "[4] Listing Pending Jobs")

# Configure retry settings
run_cmd("", "[5] Configuring Retry Settings")
run_cmd("queuectl config set max-retries 3", "Set max retries to 3")
run_cmd("queuectl config set backoff-base 2", "Set backoff base to 2")
run_cmd("queuectl config list", "Show all configuration")

print("""
\n{'='*60}
>>> [6] Starting Workers (Manual Step Required)
{'='*60}

In a NEW TERMINAL, run the following command:
  
  queuectl worker start --count 2

Watch the workers process jobs, then press Ctrl+C to stop them.
After workers stop, return to this terminal and press Enter to continue...
""")
input("Press Enter when workers have finished processing jobs...")

# Check final status
run_cmd("queuectl status", "[7] Final Queue Status")

# List completed jobs
run_cmd("queuectl list --state completed", "[8] Completed Jobs")

# Check DLQ
run_cmd("queuectl dlq list", "[9] Dead Letter Queue (Failed Jobs)")

# Retry from DLQ
run_cmd("", "[10] Retry Job from DLQ")
run_cmd("queuectl dlq retry job_retry", "Moving job_retry back to pending queue")
run_cmd("queuectl status", "Status after retry")

print("""
\n╔════════════════════════════════════════════════════════════╗
║                    Demo Complete! ✓                        ║
║                                                            ║
║  Key Features Demonstrated:                                ║
║  • Job enqueuing with different commands                   ║
║  • Multiple worker processes                               ║
║  • Automatic retry with exponential backoff                ║
║  • Dead Letter Queue for failed jobs                       ║
║  • Configuration management                                ║
║  • Persistent storage (survives restart)                   ║
╚════════════════════════════════════════════════════════════╝

Next Steps:
  1. Test restart persistence:
     - Run: python test_manual.py
     - Start workers and stop mid-processing
     - Start workers again - jobs should resume!
  
  2. Explore more commands:
     - queuectl --help
     - queuectl worker --help
     - queuectl dlq --help
     - queuectl config --help
""")
