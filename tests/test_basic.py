def test_job_acquisition(self):
    """Test worker job acquisition"""
    job = Job(id="test-job-4", command="echo 'test'")
    self.db.add_job(job)
    
    # Acquire job
    acquired = self.db.acquire_job("worker-1")
    self.assertIsNotNone(acquired)
    self.assertEqual(acquired.id, "test-job-4")
    self.assertEqual(acquired.state, "processing")
    
    # Try to acquire again - should return None (job is locked)
    acquired_again = self.db.acquire_job("worker-2")
    self.assertIsNone(acquired_again)
