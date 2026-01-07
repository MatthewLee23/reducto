"""
Download ONLY actual extraction results from Reducto (not split/classification jobs).

This script:
1. Fetches all completed jobs from Reducto
2. Filters for extraction jobs (those with extract endpoint/config)
3. Downloads results to a dedicated folder
4. Validates each result

Run: python download_extractions_only.py
"""

import os
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from dotenv import load_dotenv
from reducto import Reducto

load_dotenv()


def is_extraction_job(job) -> bool:
    """
    Determine if a job is an extraction job (vs split/parse/other).
    
    Extraction jobs typically have:
    - endpoint containing 'extract'
    - config with 'schema' or 'instructions'
    """
    # Check endpoint
    endpoint = getattr(job, 'endpoint', None) or ''
    if 'extract' in str(endpoint).lower():
        return True
    
    # Check config
    config = getattr(job, 'config', None) or {}
    if hasattr(config, 'model_dump'):
        config = config.model_dump()
    
    if isinstance(config, dict):
        # Extraction configs have 'instructions' with 'schema'
        if 'instructions' in config:
            return True
        if 'schema' in config:
            return True
    
    return False


def is_split_job(job) -> bool:
    """Check if this is a split/classification job."""
    endpoint = getattr(job, 'endpoint', None) or ''
    if 'split' in str(endpoint).lower():
        return True
    
    config = getattr(job, 'config', None) or {}
    if hasattr(config, 'model_dump'):
        config = config.model_dump()
    
    if isinstance(config, dict):
        if 'split_rules' in config:
            return True
        if 'partition_strategy' in config:
            return True
    
    return False


def get_extraction_stats(result_data: dict) -> dict:
    """Get statistics about an extraction result."""
    # Navigate to the actual result (handles various wrapper structures)
    def find_soi_rows(d):
        if not isinstance(d, dict):
            return None
        if 'soi_rows' in d:
            return d
        if 'result' in d:
            return find_soi_rows(d.get('result'))
        return None
    
    extraction = find_soi_rows(result_data)
    if not extraction:
        return {"total_rows": 0, "holdings": 0, "subtotals": 0, "totals": 0}
    
    soi_rows = extraction.get('soi_rows', [])
    
    # Handle {value, citations} wrapper
    if isinstance(soi_rows, dict):
        soi_rows = soi_rows.get('value', [])
    
    if not isinstance(soi_rows, list):
        soi_rows = []
    
    row_types = Counter()
    for row in soi_rows:
        rt = row.get('row_type')
        if isinstance(rt, dict):
            rt = rt.get('value', 'UNKNOWN')
        row_types[rt or 'UNKNOWN'] += 1
    
    return {
        "total_rows": len(soi_rows),
        "holdings": row_types.get("HOLDING", 0),
        "subtotals": row_types.get("SUBTOTAL", 0),
        "totals": row_types.get("TOTAL", 0),
    }


def main():
    api_key = os.environ.get("REDUCTO_API_KEY")
    if not api_key:
        print("ERROR: REDUCTO_API_KEY not found in environment")
        return
    
    client = Reducto(api_key=api_key)
    
    # Output directory
    output_dir = Path("extraction_downloads")
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("DOWNLOADING EXTRACTION RESULTS FROM REDUCTO")
    print("=" * 70)
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
    
    print()
    
    # Categorize jobs
    extraction_jobs = []
    split_jobs = []
    other_jobs = []
    
    for job in all_jobs:
        status = getattr(job, 'status', '').lower()
        if status != 'completed':
            continue
        
        if is_split_job(job):
            split_jobs.append(job)
        elif is_extraction_job(job):
            extraction_jobs.append(job)
        else:
            # Try to identify by endpoint
            endpoint = getattr(job, 'endpoint', None) or ''
            if 'extract' in str(endpoint).lower():
                extraction_jobs.append(job)
            elif 'split' in str(endpoint).lower():
                split_jobs.append(job)
            else:
                other_jobs.append(job)
    
    print("=" * 70)
    print("JOB CATEGORIZATION")
    print("=" * 70)
    print(f"  Extraction jobs: {len(extraction_jobs)}")
    print(f"  Split jobs:      {len(split_jobs)}")
    print(f"  Other jobs:      {len(other_jobs)}")
    print()
    
    # Check existing files
    existing_ids = set(f.stem.replace("_extract_response", "") for f in output_dir.glob("*_extract_response.json"))
    print(f"Already have {len(existing_ids)} files in {output_dir}/")
    print()
    
    # Download extraction results
    print("=" * 70)
    print("DOWNLOADING EXTRACTION RESULTS")
    print("=" * 70)
    
    downloaded = 0
    skipped_existing = 0
    skipped_empty = 0
    errors = 0
    stats_total = {"total_rows": 0, "holdings": 0, "subtotals": 0, "totals": 0}
    
    for i, job in enumerate(extraction_jobs, 1):
        job_id = getattr(job, 'job_id', None) or getattr(job, 'id', None)
        if not job_id:
            continue
        
        # Get filename from config
        config = getattr(job, 'config', None) or {}
        if hasattr(config, 'model_dump'):
            config = config.model_dump()
        
        input_url = ""
        if isinstance(config, dict):
            input_url = config.get('input', '') or config.get('document_url', '') or ''
        
        if input_url and '/' in input_url:
            filename_part = input_url.split('/')[-1]
            stem = filename_part.replace('.pdf', '') if filename_part.endswith('.pdf') else job_id
        else:
            stem = job_id
        
        # Skip if exists
        if stem in existing_ids or job_id in existing_ids:
            skipped_existing += 1
            continue
        
        output_file = output_dir / f"{stem}_extract_response.json"
        
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
                
                # Get stats
                stats = get_extraction_stats(result_data)
                
                # Skip empty results
                if stats["total_rows"] == 0:
                    skipped_empty += 1
                    print(f"[{i}/{len(extraction_jobs)}] EMPTY: {stem}")
                    continue
                
                # Build response structure
                response_data = {
                    "result": result_data,
                    "job_id": job_id,
                    "status": getattr(job_detail, 'status', 'unknown'),
                }
                
                if hasattr(job_detail, 'usage'):
                    usage = job_detail.usage
                    if hasattr(usage, 'model_dump'):
                        response_data["usage"] = usage.model_dump(mode='json')
                    elif isinstance(usage, dict):
                        response_data["usage"] = usage
                
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(response_data, f, indent=2, default=str)
                
                downloaded += 1
                for key in stats_total:
                    stats_total[key] += stats.get(key, 0)
                
                print(f"[{i}/{len(extraction_jobs)}] Downloaded: {stem} ({stats['total_rows']} rows)")
            else:
                print(f"[{i}/{len(extraction_jobs)}] No result: {job_id}")
                errors += 1
                
        except Exception as e:
            print(f"[{i}/{len(extraction_jobs)}] Error {job_id}: {e}")
            errors += 1
    
    # Summary
    print()
    print("=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)
    print(f"Downloaded:        {downloaded}")
    print(f"Skipped (exists):  {skipped_existing}")
    print(f"Skipped (empty):   {skipped_empty}")
    print(f"Errors:            {errors}")
    print()
    print(f"New data statistics:")
    print(f"  Total rows:    {stats_total['total_rows']:,}")
    print(f"  Holdings:      {stats_total['holdings']:,}")
    print(f"  Subtotals:     {stats_total['subtotals']:,}")
    print(f"  Totals:        {stats_total['totals']:,}")
    print()
    print(f"Results saved to: {output_dir}/")
    print()
    print("Next step: Run validation with:")
    print("  python validate_extractions.py")


if __name__ == "__main__":
    main()









