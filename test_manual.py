#!/usr/bin/env python3
"""Manual test script for Windows"""
import subprocess
import json
import time
import sys

def enqueue_job(job_dict):
    """Enqueue a job"""
    result = subprocess.run(
        ['queuectl', 'enqueue', json.dumps(job_dict)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode == 0

def run_cmd(cmd):
    """Run a queuectl command"""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode == 0

print("=== QueueCTL Manual Test ===\n")

# Clean slate
import os
for f in ["queuectl.db", "queuectl_config.json", "queuectl_workers.pid"]:
    if os.path.exists(f):
        os.remove(f)
        print(f"Cleaned up {f}")

print("\n1. Enqueuing test jobs...")
enqueue_job({"id": "job1", "command": "echo Hello from job 1"})
enqueue_job({"id": "job2", "command": "echo Hello from job 2"})
enqueue_job({"id": "job3", "command": "python -c \"print('Python job works!')\""})

# Add a failing job
enqueue_job({"id": "job_fail", "command": "python -c \"import sys; sys.exit(1)\"", "max_retries": 2})

print("\n2. Checking status...")
run_cmd("queuectl status")

print("\n3. Listing pending jobs...")
run_cmd("queuectl list --state pending")

print("\n4. Testing configuration...")
run_cmd("queuectl config set max-retries 5")
run_cmd("queuectl config get max-retries")

print("\n=== Setup Complete ===")
print("\nTo test workers:")
print("  1. Open a new terminal")
print("  2. Run: queuectl worker start --count 2")
print("  3. Watch the output as jobs are processed")
print("  4. After 10-15 seconds, press Ctrl+C")
print("  5. Run: queuectl status")
print("  6. Run: queuectl list --state completed")
print("  7. Run: queuectl dlq list")
