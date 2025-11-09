#!/usr/bin/env python3
"""Integration test script"""
import subprocess
import time
import json
import os
import sys

def run_command(cmd):
    """Run shell command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return result.returncode, result.stdout, result.stderr

def enqueue_job(job_dict):
    """Helper to enqueue a job using Python subprocess"""
    job_json = json.dumps(job_dict)
    # Use subprocess with list arguments to avoid shell escaping issues
    result = subprocess.run(
        ['queuectl', 'enqueue', job_json],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    return result.returncode, result.stdout, result.stderr

def test_integration():
    """Run integration tests"""
    print("=== QueueCTL Integration Tests ===\n")
    
    # Cleanup previous test data
    for f in ["queuectl.db", "queuectl_config.json", "queuectl_workers.pid"]:
        if os.path.exists(f):
            os.remove(f)
    
    # Test 1: Enqueue successful job
    print("Test 1: Enqueue successful job...")
    job1 = {"id": "job1", "command": "echo Hello World"}
    code, out, err = enqueue_job(job1)
    assert code == 0, f"Failed to enqueue job: {err}"
    print("[PASS] Job enqueued")
    print(f"  {out.strip()}\n")
    
    # Test 2: Enqueue failing job
    print("Test 2: Enqueue failing job...")
    job2 = {"id": "job2", "command": "exit 1", "max_retries": 2}
    code, out, err = enqueue_job(job2)
    assert code == 0, f"Failed to enqueue job: {err}"
    print("[PASS] Failing job enqueued")
    print(f"  {out.strip()}\n")
    
    # Test 3: Enqueue sleep job
    print("Test 3: Enqueue sleep job...")
    job3 = {"id": "job3", "command": "timeout 2" if os.name == 'nt' else "sleep 2"}
    code, out, err = enqueue_job(job3)
    assert code == 0, f"Failed to enqueue job: {err}"
    print("[PASS] Sleep job enqueued")
    print(f"  {out.strip()}\n")
    
    # Test 4: Check status
    print("Test 4: Check status...")
    code, out, err = run_command("queuectl status")
    assert code == 0, f"Status command failed: {err}"
    assert "Pending:" in out
    print("[PASS] Status command works\n")
    
    # Test 5: List jobs
    print("Test 5: List pending jobs...")
    code, out, err = run_command("queuectl list --state pending")
    assert code == 0, f"List command failed: {err}"
    assert "job1" in out or "job2" in out or "job3" in out
    print("[PASS] Jobs listed successfully\n")
    
    # Test 6: Configuration
    print("Test 6: Test configuration...")
    code, out, err = run_command("queuectl config set max-retries 5")
    assert code == 0, f"Config set failed: {err}"
    
    code, out, err = run_command("queuectl config get max-retries")
    assert code == 0, f"Config get failed: {err}"
    assert "5" in out, "Config not set correctly"
    print("[PASS] Configuration working")
    print(f"  {out.strip()}\n")
    
    # Test 7: Test duplicate job
    print("Test 7: Test duplicate job prevention...")
    job_dup = {"id": "job1", "command": "echo Duplicate"}
    code, out, err = enqueue_job(job_dup)
    assert code != 0, "Duplicate job should fail"
    print("[PASS] Duplicate job correctly rejected\n")
    
    print("=== All Integration Tests Passed ===")
    print("\nNote: Worker tests should be run manually:")
    print("  1. Run: queuectl worker start --count 2")
    print("  2. Wait for jobs to process")
    print("  3. Check: queuectl status")
    print("  4. Stop: Press Ctrl+C")

if __name__ == "__main__":
    try:
        test_integration()
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
