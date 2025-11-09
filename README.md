# QueueCTL - Background Job Queue System

A production-grade CLI-based background job queue system with worker processes, retry mechanism with exponential backoff, and Dead Letter Queue (DLQ) support.

## Features

- ✅ CLI-based job queue management
- ✅ Multiple parallel worker processes
- ✅ Exponential backoff retry mechanism
- ✅ Dead Letter Queue for permanently failed jobs
- ✅ Persistent storage using SQLite
- ✅ Graceful worker shutdown
- ✅ Configurable retry and backoff settings
- ✅ Job state tracking (pending, processing, completed, failed, dead)
- ✅ Concurrent job processing with proper locking

## Tech Stack

- **Language**: Python 3.8+
- **CLI Framework**: Click
- **Database**: SQLite
- **Process Management**: multiprocessing

## Installation

### Prerequisites

- Python 3.8 or higher
- pip

### Setup

1. Clone the repository:
git clone <your-repo-url>
cd queuectl

text

2. Install dependencies:
pip install -r requirements.txt

text

3. Install the package:
pip install -e .

text

4. Verify installation:
queuectl --help

text

## Usage

### Enqueue Jobs

Add a new job to the queue:

queuectl enqueue '{"id":"job1","command":"echo Hello World"}'
queuectl enqueue '{"id":"job2","command":"sleep 5 && echo Done"}'
queuectl enqueue '{"id":"job3","command":"python script.py"}'

text

### Start Workers

Start one or more worker processes:

Start 1 worker
queuectl worker start

Start 3 workers
queuectl worker start --count 3

text

Workers will run in the background and process jobs automatically. Press `Ctrl+C` to stop them gracefully.

### Stop Workers

Stop all running workers:

queuectl worker stop

text

### Check Status

View queue status and statistics:

queuectl status

text

Output example:
=== Queue Status ===
Pending: 5
Processing: 2
Completed: 10
Failed: 1
Dead (DLQ): 2

Active Workers: 3
PIDs: 12345, 12346, 12347

text

### List Jobs

List all jobs or filter by state:

List all jobs
queuectl list

List pending jobs
queuectl list --state pending

List completed jobs
queuectl list --state completed

List failed jobs
queuectl list --state failed

text

### Dead Letter Queue

View and manage jobs in the DLQ:

List jobs in DLQ
queuectl dlq list

Retry a specific job from DLQ
queuectl dlq retry job1

text

### Configuration

Manage system configuration:

Set max retries
queuectl config set max-retries 5

Set backoff base
queuectl config set backoff-base 3

View specific config
queuectl config get max-retries

List all configuration
queuectl config list

text

## Architecture

### Job Lifecycle

pending → processing → completed
↓ ↓
failed → dead (DLQ)
↑_____/
(retry with exponential backoff)

text

### Components

1. **CLI Layer** (`cli.py`): Handles user commands and interaction
2. **Database Layer** (`db.py`): SQLite-based persistent storage with concurrency control
3. **Worker Layer** (`worker.py`): Executes jobs in separate processes
4. **Config Layer** (`config.py`): Manages system configuration
5. **Models Layer** (`models.py`): Data structures and schemas

### Data Persistence

- **Storage**: SQLite database (`queuectl.db`)
- **Locking**: Row-level locking prevents duplicate job processing
- **Durability**: All job state persists across restarts

### Concurrency Model

- Multiple worker processes can run in parallel
- Database locking ensures no race conditions
- Each worker acquires jobs atomically
- Graceful shutdown ensures jobs complete before exit

### Retry Logic

Failed jobs retry automatically using **exponential backoff**:

delay = backoff_base ^ attempts (seconds)

text

Example with base=2:
- Attempt 1: 2¹ = 2 seconds
- Attempt 2: 2² = 4 seconds
- Attempt 3: 2³ = 8 seconds

After exhausting retries, jobs move to the Dead Letter Queue.

## Testing

### Run Unit Tests

python -m pytest tests/test_basic.py -v

text

### Run Integration Tests

python tests/test_integration.py

text

### Manual Testing Script

#!/bin/bash

echo "=== Testing QueueCTL ==="

Clean slate
rm -f queuectl.db queuectl_config.json queuectl_workers.pid

Test 1: Enqueue jobs
echo -e "\n1. Enqueuing jobs..."
queuectl enqueue '{"id":"job1","command":"echo Test 1"}'
queuectl enqueue '{"id":"job2","command":"sleep 2 && echo Test 2"}'
queuectl enqueue '{"id":"job3","command":"exit 1"}'

Test 2: Check status
echo -e "\n2. Checking status..."
queuectl status

Test 3: Start workers in background
echo -e "\n3. Starting workers..."
queuectl worker start --count 2 &
WORKER_PID=$!

Wait for jobs to process
sleep 5

Test 4: Check status again
echo -e "\n4. Status after processing..."
queuectl status

Test 5: List completed jobs
echo -e "\n5. Completed jobs..."
queuectl list --state completed

Test 6: Check DLQ
echo -e "\n6. Dead Letter Queue..."
queuectl dlq list

Cleanup
kill $WORKER_PID 2>/dev/null
queuectl worker stop

echo -e "\n=== Tests Complete ==="

text

## Assumptions & Trade-offs

### Assumptions

1. Jobs are shell commands that can be executed via `subprocess`
2. Job IDs are unique and provided by the user
3. Commands complete within 5 minutes (configurable timeout)
4. Workers run on the same machine as the queue
5. Moderate job volume (SQLite handles ~100k jobs efficiently)

### Trade-offs

1. **SQLite vs Redis**: SQLite chosen for zero-dependency simplicity; Redis would offer better performance at scale
2. **Process vs Thread**: Processes used for true parallelism and isolation; threads would be lighter but share memory
3. **Polling vs Events**: Workers poll for jobs; event-driven would be more efficient but complex
4. **File-based config**: Simple JSON file used; production might use environment variables or remote config

### Simplifications

- No job priority queues (could be added via priority column)
- No scheduled/delayed jobs (could use run_at field)
- Basic command execution (no stdin/environment customization)
- No web dashboard (CLI-only interface)

## Bonus Features

Optional enhancements that could be added:

- [ ] Job timeout handling
- [ ] Priority queues
- [ ] Scheduled jobs (run_at timestamp)
- [ ] Job output logging to files
- [ ] Execution metrics and statistics
- [ ] Web dashboard for monitoring
- [ ] Job dependencies
- [ ] Rate limiting

## Demo Video

[Link to demo video on Google Drive]

## Project Structure

queuectl/
├── queuectl/
│ ├── init.py
│ ├── cli.py # CLI commands
│ ├── queue.py # Queue management
│ ├── worker.py # Worker processes
│ ├── config.py # Configuration
│ ├── models.py # Data models
│ └── db.py # Database layer
├── tests/
│ ├── test_basic.py # Unit tests
│ └── test_integration.py # Integration tests
├── setup.py # Package setup
├── requirements.txt # Dependencies
├── README.md # This file
└── design.md # Architecture details

text

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License

## Author

[Your Name]

## Submission Checklist

- [x] All required commands functional
- [x] Jobs persist after restart
- [x] Retry and backoff implemented correctly
- [x] DLQ operational
- [x] CLI user-friendly and documented
- [x] Code is modular and maintainable
- [x] Includes tests verifying main flows
- [x] README with setup and usage
- [x] Architecture documentation