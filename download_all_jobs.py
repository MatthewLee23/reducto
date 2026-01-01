"""
Download results from all completed Reducto jobs.
This retrieves results for the $930 worth of jobs you already paid for.

Run: python download_all_jobs.py
"""

import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from reducto import Reducto

load_dotenv()


def main():
    api_key = os.environ.get("REDUCTO_API_KEY")
    if not api_key:
        print("ERROR: REDUCTO_API_KEY not found in environment")
        return
    
    client = Reducto(api_key=api_key)
    
    # Output directories
    extract_urls_dir = Path("extract_urls")
    split_dir = Path("split_results")
    extract_urls_dir.mkdir(exist_ok=True)
    split_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("DOWNLOADING ALL COMPLETED JOB RESULTS")
    print("=" * 60)
    print()
    print("Fetching job list from Reducto...")
    
    # Get all jobs with pagination
    cursor = None
    all_jobs = []
    
    while True:
        if cursor:
            response = client.job.get_all(limit=100, cursor=cursor, exclude_configs=False)
        else:
            response = client.job.get_all(limit=100, exclude_configs=False)
        
        all_jobs.extend(response.jobs)
        print(f"  Fetched {len(all_jobs)} jobs...")
        
        if response.next_cursor:
            cursor = response.next_cursor
        else:
            break
    
    # Filter to completed jobs only
    completed_jobs = [j for j in all_jobs if getattr(j, 'status', '').lower() == 'completed']
    print()
    print(f"Found {len(completed_jobs)} completed jobs")
    print()
    
    # Check which ones we already have
    existing_files = set(f.stem.replace("_extract_response", "") for f in extract_urls_dir.glob("*_extract_response.json"))
    print(f"Already have {len(existing_files)} extract responses on disk")
    
    # Download results
    downloaded = 0
    skipped = 0
    errors = 0
    
    for i, job in enumerate(completed_jobs, 1):
        job_id = getattr(job, 'job_id', None) or getattr(job, 'id', None)
        if not job_id:
            continue
        
        # Try to get a filename from job config or use job_id
        config = getattr(job, 'config', None) or {}
        if hasattr(config, 'model_dump'):
            config = config.model_dump()
        
        # Extract filename from input URL or use job_id
        input_url = ""
        if isinstance(config, dict):
            input_url = config.get('input', '') or config.get('document_url', '') or ''
        
        # Try to extract stem from input URL
        if input_url and '/' in input_url:
            filename_part = input_url.split('/')[-1]
            if filename_part.endswith('.pdf'):
                stem = filename_part.replace('.pdf', '')
            else:
                stem = job_id
        else:
            stem = job_id
        
        # Skip if already exists
        output_file = extract_urls_dir / f"{stem}_extract_response.json"
        if output_file.exists():
            skipped += 1
            continue
        
        # Get full job details including result
        try:
            job_detail = client.job.get(job_id)
            
            if hasattr(job_detail, 'result') and job_detail.result:
                result = job_detail.result
                if hasattr(result, 'model_dump'):
                    result_data = result.model_dump(mode='json')
                elif isinstance(result, dict):
                    result_data = result
                else:
                    result_data = {"raw": str(result)}
                
                # Build response structure
                response_data = {
                    "result": result_data,
                    "job_id": job_id,
                    "status": getattr(job_detail, 'status', 'unknown'),
                }
                
                # Add usage if available
                if hasattr(job_detail, 'usage'):
                    usage = job_detail.usage
                    if hasattr(usage, 'model_dump'):
                        response_data["usage"] = usage.model_dump(mode='json')
                    elif isinstance(usage, dict):
                        response_data["usage"] = usage
                
                with open(output_file, "w") as f:
                    json.dump(response_data, f, indent=2, default=str)
                
                downloaded += 1
                print(f"[{i}/{len(completed_jobs)}] Downloaded: {stem}")
            else:
                print(f"[{i}/{len(completed_jobs)}] No result: {job_id}")
                errors += 1
                
        except Exception as e:
            print(f"[{i}/{len(completed_jobs)}] Error {job_id}: {e}")
            errors += 1
    
    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (already exists): {skipped}")
    print(f"Errors: {errors}")
    print()
    print(f"Results saved to: {extract_urls_dir}/")
    print()
    print("Next step: Run validation with:")
    print("  python validate_existing.py")


if __name__ == "__main__":
    main()

