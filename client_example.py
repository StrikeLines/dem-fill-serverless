#!/usr/bin/env python3
"""
Example client for triggering DEM inpainting jobs on RunPod serverless endpoint.

This script:
1. Uploads a local GeoTIFF to the S3 input bucket
2. Triggers a RunPod serverless job
3. Polls for job completion
4. Reports the result

Usage:
    python client_example.py /path/to/local_dem.tif --filename my_test_tile.tif

Environment variables required:
    RUNPOD_API_KEY - Your RunPod API key
    RUNPOD_ENDPOINT_ID - Your RunPod serverless endpoint ID
    AWS_ACCESS_KEY_ID - AWS access key
    AWS_SECRET_ACCESS_KEY - AWS secret key
    AWS_DEFAULT_REGION - AWS region (default: us-east-1)
"""

import os
import json
import time
import argparse
import sys
from typing import Dict, Any, Optional

import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError


# Configuration
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID") 

S3_BUCKET = os.environ.get("DEM_S3_BUCKET", "dem-fill-serverless-file-store")
S3_INPUT_PREFIX = os.environ.get("DEM_INPUT_PREFIX", "to-process/")
S3_OUTPUT_PREFIX = os.environ.get("DEM_OUTPUT_PREFIX", "completed/")

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Validate required environment variables
if not RUNPOD_API_KEY:
    print("ERROR: RUNPOD_API_KEY environment variable not set")
    sys.exit(1)

if not RUNPOD_ENDPOINT_ID:
    print("ERROR: RUNPOD_ENDPOINT_ID environment variable not set")
    sys.exit(1)


def get_s3_client():
    """Create and return S3 client with error handling."""
    try:
        return boto3.client(
            "s3",
            region_name=AWS_REGION,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
    except NoCredentialsError:
        print("ERROR: AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        sys.exit(1)


def upload_to_process(local_path: str, filename: str) -> str:
    """
    Upload a local file to the S3 input bucket.
    
    Args:
        local_path: Path to local file
        filename: Filename to use in S3
        
    Returns:
        S3 key of uploaded file
    """
    s3 = get_s3_client()
    key = f"{S3_INPUT_PREFIX}{filename}"
    
    try:
        print(f"Uploading {local_path} to s3://{S3_BUCKET}/{key}")
        s3.upload_file(local_path, S3_BUCKET, key)
        print(f"✓ Upload successful")
        return key
    except ClientError as e:
        print(f"ERROR uploading to S3: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"ERROR: Local file not found: {local_path}")
        sys.exit(1)


def trigger_job(filename: str) -> Dict[str, Any]:
    """
    Trigger a RunPod serverless job.
    
    Args:
        filename: Filename in S3 to process
        
    Returns:
        RunPod job response
    """
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "input": {
            "filename": filename
        }
    }
    
    try:
        print(f"Triggering RunPod job for filename: {filename}")
        resp = requests.post(url, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()
        
        result = resp.json()
        print(f"✓ Job triggered successfully")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR triggering RunPod job: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        sys.exit(1)


def check_job_status(job_id: str) -> Dict[str, Any]:
    """
    Check the status of a RunPod job.
    
    Args:
        job_id: RunPod job ID
        
    Returns:
        Job status response
    """
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{job_id}"
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
    }
    
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR checking job status: {e}")
        return {"status": "UNKNOWN", "error": str(e)}


def wait_for_completion(job_id: str, timeout: int = 1800, poll_interval: int = 10) -> Optional[Dict[str, Any]]:
    """
    Wait for job completion with polling.
    
    Args:
        job_id: RunPod job ID
        timeout: Maximum time to wait in seconds
        poll_interval: How often to check status in seconds
        
    Returns:
        Final job result or None if timeout
    """
    print(f"Waiting for job {job_id} to complete...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status_response = check_job_status(job_id)
        status = status_response.get("status")
        
        if status == "COMPLETED":
            print("✓ Job completed successfully!")
            return status_response.get("output")
        elif status == "FAILED":
            print("✗ Job failed!")
            error = status_response.get("error", "Unknown error")
            print(f"Error: {error}")
            return status_response
        elif status in ["IN_QUEUE", "IN_PROGRESS"]:
            elapsed = int(time.time() - start_time)
            print(f"Job status: {status} (elapsed: {elapsed}s)")
        else:
            print(f"Unknown job status: {status}")
        
        time.sleep(poll_interval)
    
    print(f"✗ Job did not complete within {timeout} seconds")
    return None


def check_output_exists(filename: str) -> bool:
    """Check if the output file exists in S3."""
    s3 = get_s3_client()
    key = f"{S3_OUTPUT_PREFIX}{filename}"
    
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Process DEM files using RunPod serverless")
    parser.add_argument("local_input", help="Path to local GeoTIFF to upload and process")
    parser.add_argument("--filename", help="Filename to use in S3 (default: basename of input)")
    parser.add_argument("--timeout", type=int, default=1800, help="Job timeout in seconds (default: 1800)")
    parser.add_argument("--poll-interval", type=int, default=10, help="Status check interval in seconds (default: 10)")
    parser.add_argument("--skip-upload", action="store_true", help="Skip upload step (file must already be in S3)")
    
    args = parser.parse_args()
    
    local_input = args.local_input
    filename = args.filename or os.path.basename(local_input)
    
    print("=== DEM Fill Serverless Client ===")
    print(f"Input file: {local_input}")
    print(f"S3 filename: {filename}")
    print(f"RunPod endpoint: {RUNPOD_ENDPOINT_ID}")
    print()
    
    # Step 1: Upload to S3 (unless skipped)
    if not args.skip_upload:
        upload_to_process(local_input, filename)
    else:
        print(f"Skipping upload - assuming {filename} already exists in S3")
    
    # Step 2: Trigger RunPod job
    job_response = trigger_job(filename)
    job_id = job_response.get("id")
    
    if not job_id:
        print(f"ERROR: No job ID returned. Response: {job_response}")
        sys.exit(1)
    
    print(f"Job ID: {job_id}")
    print()
    
    # Step 3: Wait for completion
    final_result = wait_for_completion(job_id, timeout=args.timeout, poll_interval=args.poll_interval)
    
    if final_result is None:
        print("Job did not complete in time")
        sys.exit(1)
    
    # Step 4: Report results
    print("\n=== Final Result ===")
    print(json.dumps(final_result, indent=2))
    
    # Check if output file exists
    if final_result.get("status") == "success":
        output_location = f"s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}{filename}"
        print(f"\n✓ Completed file should be at: {output_location}")
        
        if check_output_exists(filename):
            print("✓ Output file confirmed to exist in S3")
        else:
            print("⚠ Warning: Output file not found in S3")


if __name__ == "__main__":
    main()