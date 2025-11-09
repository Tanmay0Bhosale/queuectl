import click
import json
import sys
from pathlib import Path
from .db import JobDatabase
from .config import Config
from .models import Job
from .worker import WorkerManager

# Windows-compatible output symbols
OK = "[OK]"
ERR = "[ERR]"
WARN = "[WARN]"

@click.group()
@click.pass_context
def cli(ctx):
    """QueueCTL - A CLI-based background job queue system"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = Config()
    ctx.obj['db'] = JobDatabase(ctx.obj['config'].get('db_path'))

@cli.command()
@click.argument('job_json')
@click.pass_context
def enqueue(ctx, job_json):
    """
    Enqueue a new job
    
    Example: queuectl enqueue "{\"id\":\"job1\",\"command\":\"echo Hello\"}"
    """
    try:
        job_data = json.loads(job_json)
        
        # Apply default max_retries from config if not specified
        if 'max_retries' not in job_data:
            job_data['max_retries'] = ctx.obj['config'].get('max_retries', 3)
        
        job = Job.from_dict(job_data)
        db = ctx.obj['db']
        
        if db.add_job(job):
            click.echo(f"{OK} Job '{job.id}' enqueued successfully")
        else:
            click.echo(f"{ERR} Job '{job.id}' already exists", err=True)
            sys.exit(1)
            
    except json.JSONDecodeError:
        click.echo(f"{ERR} Invalid JSON format", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"{ERR} Error: {e}", err=True)
        sys.exit(1)

@cli.group()
def worker():
    """Manage workers"""
    pass

@worker.command('start')
@click.option('--count', default=1, help='Number of workers to start')
@click.pass_context
def worker_start(ctx, count):
    """Start worker processes"""
    try:
        manager = WorkerManager(ctx.obj['config'].config_path)
        
        # Check if workers already running
        active_workers = manager.get_active_workers()
        if active_workers:
            click.echo(f"{WARN} Workers already running (PIDs: {active_workers})")
            click.echo("  Stop them first with: queuectl worker stop")
            return
        
        manager.start_workers(count)
        
        # Keep main process alive to manage workers
        click.echo(f"{OK} {count} worker(s) started. Press Ctrl+C to stop.")
        try:
            for worker_info in manager.processes:
                worker_info['process'].join()
        except KeyboardInterrupt:
            click.echo(f"\n{WARN} Stopping workers...")
            manager.stop_workers()
            
    except Exception as e:
        click.echo(f"{ERR} Error: {e}", err=True)
        sys.exit(1)

@worker.command('stop')
@click.pass_context
def worker_stop(ctx):
    """Stop running workers"""
    try:
        import signal
        manager = WorkerManager(ctx.obj['config'].config_path)
        pids = manager.get_active_workers()
        
        if not pids:
            click.echo(f"{WARN} No active workers found")
            return
        
        # Send SIGTERM to each worker
        for pid in pids:
            try:
                import os
                os.kill(pid, signal.SIGTERM)
                click.echo(f"{OK} Sent stop signal to worker PID {pid}")
            except ProcessLookupError:
                click.echo(f"{WARN} Worker PID {pid} not found")
        
        # Clean up PID file
        pid_file = Path("queuectl_workers.pid")
        if pid_file.exists():
            pid_file.unlink()
        
        click.echo(f"{OK} Workers stopped")
        
    except Exception as e:
        click.echo(f"{ERR} Error: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def status(ctx):
    """Show job queue status"""
    db = ctx.obj['db']
    stats = db.get_stats()
    
    click.echo("\n=== Queue Status ===")
    click.echo(f"Pending:    {stats.get('pending', 0)}")
    click.echo(f"Processing: {stats.get('processing', 0)}")
    click.echo(f"Completed:  {stats.get('completed', 0)}")
    click.echo(f"Failed:     {stats.get('failed', 0)}")
    click.echo(f"Dead (DLQ): {stats.get('dead', 0)}")
    
    # Show active workers
    manager = WorkerManager(ctx.obj['config'].config_path)
    active_workers = manager.get_active_workers()
    click.echo(f"\nActive Workers: {len(active_workers)}")
    if active_workers:
        click.echo(f"PIDs: {', '.join(map(str, active_workers))}")

@cli.command('list')
@click.option('--state', help='Filter by state (pending, processing, completed, failed, dead)')
@click.pass_context
def list_jobs(ctx, state):
    """List jobs"""
    db = ctx.obj['db']
    jobs = db.list_jobs(state)
    
    if not jobs:
        click.echo(f"No jobs found{' with state: ' + state if state else ''}")
        return
    
    click.echo(f"\n=== Jobs{' (' + state + ')' if state else ''} ===\n")
    
    for job in jobs:
        click.echo(f"ID: {job.id}")
        click.echo(f"  Command:  {job.command}")
        click.echo(f"  State:    {job.state}")
        click.echo(f"  Attempts: {job.attempts}/{job.max_retries}")
        click.echo(f"  Created:  {job.created_at}")
        if job.last_error:
            click.echo(f"  Error:    {job.last_error[:100]}")
        if job.next_retry_at:
            click.echo(f"  Retry at: {job.next_retry_at}")
        click.echo()

@cli.group()
def dlq():
    """Dead Letter Queue operations"""
    pass

@dlq.command('list')
@click.pass_context
def dlq_list(ctx):
    """List jobs in Dead Letter Queue"""
    db = ctx.obj['db']
    dead_jobs = db.list_jobs('dead')
    
    if not dead_jobs:
        click.echo("No jobs in Dead Letter Queue")
        return
    
    click.echo(f"\n=== Dead Letter Queue ({len(dead_jobs)} jobs) ===\n")
    
    for job in dead_jobs:
        click.echo(f"ID: {job.id}")
        click.echo(f"  Command:  {job.command}")
        click.echo(f"  Attempts: {job.attempts}")
        click.echo(f"  Error:    {job.last_error[:150] if job.last_error else 'N/A'}")
        click.echo(f"  Failed:   {job.updated_at}")
        click.echo()

@dlq.command('retry')
@click.argument('job_id')
@click.pass_context
def dlq_retry(ctx, job_id):
    """Retry a job from Dead Letter Queue"""
    db = ctx.obj['db']
    job = db.get_job(job_id)
    
    if not job:
        click.echo(f"{ERR} Job '{job_id}' not found", err=True)
        sys.exit(1)
    
    if job.state != 'dead':
        click.echo(f"{ERR} Job '{job_id}' is not in DLQ (state: {job.state})", err=True)
        sys.exit(1)
    
    # Reset job for retry
    job.state = 'pending'
    job.attempts = 0
    job.last_error = None
    job.next_retry_at = None
    
    db.update_job(job)
    click.echo(f"{OK} Job '{job_id}' moved from DLQ back to pending queue")

@cli.group()
def config():
    """Configuration management"""
    pass

@config.command('set')
@click.argument('key')
@click.argument('value')
@click.pass_context
def config_set(ctx, key, value):
    """Set configuration value"""
    cfg = ctx.obj['config']
    
    # Convert value to appropriate type
    if key in ['max_retries', 'backoff_base', 'worker_check_interval']:
        try:
            value = int(value)
        except ValueError:
            click.echo(f"{ERR} {key} must be an integer", err=True)
            sys.exit(1)
    
    cfg.set(key, value)
    click.echo(f"{OK} Configuration updated: {key} = {value}")

@config.command('get')
@click.argument('key', required=False)
@click.pass_context
def config_get(ctx, key):
    """Get configuration value(s)"""
    cfg = ctx.obj['config']
    
    if key:
        value = cfg.get(key)
        if value is None:
            click.echo(f"{ERR} Configuration key '{key}' not found", err=True)
            sys.exit(1)
        click.echo(f"{key}: {value}")
    else:
        click.echo("\n=== Configuration ===")
        for k, v in cfg.get_all().items():
            click.echo(f"{k}: {v}")

@config.command('list')
@click.pass_context
def config_list(ctx):
    """List all configuration"""
    cfg = ctx.obj['config']
    click.echo("\n=== Configuration ===")
    for k, v in cfg.get_all().items():
        click.echo(f"{k}: {v}")

if __name__ == '__main__':
    cli()
