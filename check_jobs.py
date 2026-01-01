"""
List and cancel all running/pending jobs on Reducto.
Run: python check_jobs.py
"""

import os
from dotenv import load_dotenv
from reducto import Reducto

load_dotenv()

def main():
    api_key = os.environ.get("REDUCTO_API_KEY")
    if not api_key:
        print("ERROR: REDUCTO_API_KEY not found in environment")
        return
    
    client = Reducto(api_key=api_key)
    
    print("Fetching all jobs from Reducto...")
    print()
    
    # Get all jobs with pagination
    cursor = None
    all_jobs = []
    
    while True:
        if cursor:
            response = client.job.get_all(limit=100, cursor=cursor, exclude_configs=True)
        else:
            response = client.job.get_all(limit=100, exclude_configs=True)
        
        all_jobs.extend(response.jobs)
        
        if response.next_cursor:
            cursor = response.next_cursor
        else:
            break
    
    print(f"Found {len(all_jobs)} total jobs")
    print()
    
    # Categorize jobs
    pending = []
    running = []
    completed = []
    failed = []
    other = []
    
    for job in all_jobs:
        status = getattr(job, 'status', 'unknown').lower()
        if status == 'pending':
            pending.append(job)
        elif status in ['running', 'processing', 'inprogress', 'completing']:
            running.append(job)
        elif status == 'completed':
            completed.append(job)
        elif status == 'failed':
            failed.append(job)
        else:
            other.append(job)
    
    print("Job Summary:")
    print(f"  Pending:   {len(pending)}")
    print(f"  Running:   {len(running)}")
    print(f"  Completed: {len(completed)}")
    print(f"  Failed:    {len(failed)}")
    print(f"  Other:     {len(other)}")
    print()
    
    # Cancel pending and running jobs
    jobs_to_cancel = pending + running
    
    if not jobs_to_cancel:
        print("No pending or running jobs to cancel.")
        return
    
    print(f"Cancelling {len(jobs_to_cancel)} jobs...")
    
    cancelled = 0
    errors = 0
    
    for job in jobs_to_cancel:
        job_id = getattr(job, 'job_id', None) or getattr(job, 'id', None)
        if not job_id:
            print(f"  [SKIP] Could not get job ID")
            continue
        
        try:
            client.job.cancel(job_id)
            print(f"  [CANCELLED] {job_id}")
            cancelled += 1
        except Exception as e:
            print(f"  [ERROR] {job_id}: {e}")
            errors += 1
    
    print()
    print(f"Done. Cancelled: {cancelled}, Errors: {errors}")


if __name__ == "__main__":
    main()
