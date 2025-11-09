import subprocess
import time
import signal
import sys
import json
import os
from datetime import datetime, timedelta
from multiprocessing import Process, Event
from pathlib import Path
from typing import Optional
from .db import JobDatabase
from .config import Config
from .models import Job

class Worker:
    """Worker process that executes jobs"""
    
    def __init__(self, worker_id: str, db_path: str, config_path: str, stop_event: Event):
        self.worker_id = worker_id
        self.db = JobDatabase(db_path)
        self.config = Config(config_path)
        self.stop_event = stop_event
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n[Worker {self.worker_id}] Received shutdown signal, finishing current job...")
        self.running = False
    
    def run(self):
        """Main worker loop"""
        print(f"[Worker {self.worker_id}] Started")
        
        check_interval = self.config.get("worker_check_interval", 1)
        
        while self.running and not self.stop_event.is_set():
            try:
                job = self.db.acquire_job(self.worker_id)
                
                if job:
                    print(f"[Worker {self.worker_id}] Processing job {job.id}")
                    self._execute_job(job)
                else:
                    time.sleep(check_interval)
                    
            except Exception as e:
                print(f"[Worker {self.worker_id}] Error: {e}")
                time.sleep(check_interval)
        
        print(f"[Worker {self.worker_id}] Stopped")
    
    def _execute_job(self, job: Job):
        """Execute a job command"""
        try:
            # Execute the command
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Job succeeded
                job.state = "completed"
                job.last_error = None
                print(f"[Worker {self.worker_id}] Job {job.id} completed successfully")
                if result.stdout:
                    print(f"  Output: {result.stdout.strip()}")
            else:
                # Job failed
                self._handle_job_failure(job, f"Exit code {result.returncode}: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self._handle_job_failure(job, "Job execution timeout")
        except Exception as e:
            self._handle_job_failure(job, str(e))
        finally:
            self.db.update_job(job)
            self.db.release_job(job.id)
    
    def _handle_job_failure(self, job: Job, error: str):
        """Handle job failure with exponential backoff retry logic"""
        job.attempts += 1
        job.last_error = error
        
        max_retries = self.config.get("max_retries", 3)
        
        if job.attempts >= max_retries:
            # Move to dead letter queue
            job.state = "dead"
            job.next_retry_at = None
            print(f"[Worker {self.worker_id}] Job {job.id} moved to DLQ after {job.attempts} attempts")
        else:
            # Calculate exponential backoff
            backoff_base = self.config.get("backoff_base", 2)
            delay_seconds = backoff_base ** job.attempts
            next_retry = datetime.utcnow() + timedelta(seconds=delay_seconds)
            job.next_retry_at = next_retry.isoformat() + "Z"
            job.state = "failed"
            print(f"[Worker {self.worker_id}] Job {job.id} failed (attempt {job.attempts}/{max_retries}), retry in {delay_seconds}s")
            print(f"  Error: {error}")


class WorkerManager:
    """Manages multiple worker processes"""
    
    def __init__(self, config_path: str = "queuectl_config.json"):
        self.config = Config(config_path)
        self.processes = []
        self.stop_event = Event()
        self.pid_file = Path("queuectl_workers.pid")
    
    def start_workers(self, count: int):
        """Start multiple worker processes"""
        db_path = self.config.get("db_path", "queuectl.db")
        
        for i in range(count):
            worker_id = f"worker-{i+1}"
            process = Process(
                target=self._worker_wrapper,
                args=(worker_id, db_path, self.config.config_path, self.stop_event)
            )
            process.start()
            self.processes.append({
                'id': worker_id,
                'process': process,
                'pid': process.pid
            })
        
        self._save_pids()
        print(f"Started {count} worker(s)")
    
    @staticmethod
    def _worker_wrapper(worker_id: str, db_path: str, config_path: str, stop_event: Event):
        """Wrapper to run worker in subprocess"""
        worker = Worker(worker_id, db_path, config_path, stop_event)
        worker.run()
    
    def stop_workers(self):
        """Stop all worker processes gracefully"""
        self.stop_event.set()
        
        for worker_info in self.processes:
            process = worker_info['process']
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
        
        self.processes.clear()
        if self.pid_file.exists():
            self.pid_file.unlink()
        
        print("All workers stopped")
    
    def _save_pids(self):
        """Save worker PIDs to file"""
        pids = [w['pid'] for w in self.processes]
        with open(self.pid_file, 'w') as f:
            json.dump(pids, f)
    
    def get_active_workers(self) -> list:
        """Get list of active worker PIDs"""
        if not self.pid_file.exists():
            return []
        
        try:
            with open(self.pid_file, 'r') as f:
                pids = json.load(f)
            
            # Verify PIDs are still running
            active_pids = []
            for pid in pids:
                try:
                    # Check if process exists (works on both Windows and Unix)
                    os.kill(pid, 0)
                    active_pids.append(pid)
                except (OSError, ProcessLookupError):
                    # Process doesn't exist
                    pass
            
            # If no active PIDs, clean up the file
            if not active_pids and self.pid_file.exists():
                self.pid_file.unlink()
            
            return active_pids
        except:
            return []
