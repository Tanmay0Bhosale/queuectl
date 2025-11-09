import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from contextlib import contextmanager
from .models import Job

class JobDatabase:
    """Handles all database operations with proper locking"""
    
    def __init__(self, db_path: str = "queuectl.db"):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper settings for concurrency"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level='IMMEDIATE',
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_error TEXT,
                    next_retry_at TEXT,
                    locked_by TEXT,
                    locked_at TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_state ON jobs(state)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_next_retry ON jobs(next_retry_at)
            """)
    
    def add_job(self, job: Job) -> bool:
        """Add a new job to the database"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO jobs (id, command, state, attempts, max_retries,
                                    created_at, updated_at, last_error, next_retry_at,
                                    locked_by, locked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.id, job.command, job.state, job.attempts, job.max_retries,
                    job.created_at, job.updated_at, job.last_error, job.next_retry_at,
                    None, None
                ))
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_job(row)
            return None
    
    def acquire_job(self, worker_id: str) -> Optional[Job]:
        """Acquire next available job with proper locking"""
        with self._get_connection() as conn:
            # Find jobs ready to process
            now = datetime.utcnow().isoformat() + "Z"
            
            cursor = conn.execute("""
                SELECT * FROM jobs 
                WHERE state IN ('pending', 'failed')
                AND (locked_by IS NULL OR locked_at < datetime('now', '-5 minutes'))
                AND (next_retry_at IS NULL OR next_retry_at <= ?)
                ORDER BY created_at ASC
                LIMIT 1
            """, (now,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            job_id = row['id']
            
            # Lock the job and update state to processing
            cursor = conn.execute("""
                UPDATE jobs 
                SET locked_by = ?, locked_at = ?, state = 'processing', updated_at = ?
                WHERE id = ? AND (locked_by IS NULL OR locked_at < datetime('now', '-5 minutes'))
            """, (worker_id, now, now, job_id))
            
            # Check if we successfully acquired the job
            if cursor.rowcount > 0:
                # Fetch the updated job
                cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
                updated_row = cursor.fetchone()
                if updated_row:
                    return self._row_to_job(updated_row)
            
            return None
    
    def update_job(self, job: Job) -> bool:
        """Update job in database"""
        job.updated_at = datetime.utcnow().isoformat() + "Z"
        
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE jobs 
                SET command = ?, state = ?, attempts = ?, max_retries = ?,
                    updated_at = ?, last_error = ?, next_retry_at = ?
                WHERE id = ?
            """, (
                job.command, job.state, job.attempts, job.max_retries,
                job.updated_at, job.last_error, job.next_retry_at, job.id
            ))
            return conn.total_changes > 0
    
    def release_job(self, job_id: str):
        """Release lock on a job"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE jobs 
                SET locked_by = NULL, locked_at = NULL
                WHERE id = ?
            """, (job_id,))
    
    def list_jobs(self, state: Optional[str] = None) -> List[Job]:
        """List jobs, optionally filtered by state"""
        with self._get_connection() as conn:
            if state:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE state = ? ORDER BY created_at DESC",
                    (state,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC"
                )
            
            return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> dict:
        """Get job statistics"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT state, COUNT(*) as count 
                FROM jobs 
                GROUP BY state
            """)
            
            stats = {row['state']: row['count'] for row in cursor.fetchall()}
            return stats
    
    def _row_to_job(self, row) -> Job:
        """Convert database row to Job object"""
        return Job(
            id=row['id'],
            command=row['command'],
            state=row['state'],
            attempts=row['attempts'],
            max_retries=row['max_retries'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            last_error=row['last_error'],
            next_retry_at=row['next_retry_at']
        )
