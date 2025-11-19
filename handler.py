import os
import subprocess
import tempfile
import logging
import traceback

import boto3
import runpod

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration via environment variables ---

S3_BUCKET = os.environ.get("DEM_S3_BUCKET", "dem-fill-serverless-file-store")
INPUT_PREFIX = os.environ.get("DEM_INPUT_PREFIX", "to-process/")
OUTPUT_PREFIX = os.environ.get("DEM_OUTPUT_PREFIX", "completed/")

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# AWS creds come from:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
# which must be set in the Runpod serverless endpoint configuration.

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)


def run_dem_inpainting(input_path: str, output_path: str):
    """
    Calls the dem-fill inference command, using the same settings
    as in the original init script.

    Expected behavior:
        - Reads input_path
        - Writes output_path
    
    Note: This command may need adjustment based on the actual dem-fill CLI interface.
    The current implementation assumes an --output_img parameter exists.
    """
    
    logger.info(f"Running DEM inpainting on {input_path}")
    
    # Command based on the specification - may need adjustment
    cmd = [
        "python",
        "run.py",
        "-p",
        "test",
        "-c",
        "/workspace/shared/dem-fill/config/dem_completion.json",
        "--resume_state",
        "/workspace/shared/dem-fill/pretrained/20",
        "--n_timestep",
        "100",
        "--input_img",
        input_path,
        # Note: This output argument may need to be adjusted based on actual dem-fill interface
        "--output_img",
        output_path,
    ]

    logger.info(f"Executing command: {' '.join(cmd)}")
    
    try:
        # Run the command from the dem-fill directory
        result = subprocess.run(
            cmd, 
            cwd="/workspace/shared/dem-fill",
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("DEM inpainting completed successfully")
        logger.debug(f"stdout: {result.stdout}")
        
        return result
        
    except subprocess.CalledProcessError as e:
        logger.error(f"DEM inpainting failed with return code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise


def handler(event):
    """
    Expected event["input"] structure:

    {
      "filename": "my_tile_001.tif"
    }

    The file is assumed to be at:
        s3://<bucket>/<INPUT_PREFIX>/<filename>

    Output will be written to:
        s3://<bucket>/<OUTPUT_PREFIX>/<filename>
    """
    
    try:
        logger.info(f"Processing event: {event}")
        
        job_input = event.get("input") or {}
        filename = job_input.get("filename")
        
        if not filename:
            raise ValueError("Missing 'filename' in event['input'].")

        # S3 keys
        input_key = f"{INPUT_PREFIX}{filename}"
        output_key = f"{OUTPUT_PREFIX}{filename}"

        logger.info(f"Processing file: {filename}")
        logger.info(f"Input S3 key: {input_key}")
        logger.info(f"Output S3 key: {output_key}")

        with tempfile.TemporaryDirectory() as tmpdir:
            local_in = os.path.join(tmpdir, "input.tif")
            local_out = os.path.join(tmpdir, "output.tif")

            logger.info("Downloading input file from S3...")
            # 1. Download input from S3
            s3.download_file(S3_BUCKET, input_key, local_in)
            logger.info(f"Downloaded {input_key} to {local_in}")

            # 2. Run DEM inpainting
            logger.info("Starting DEM inpainting inference...")
            run_dem_inpainting(local_in, local_out)

            # Verify output file exists
            if not os.path.exists(local_out):
                raise RuntimeError(f"Output file {local_out} was not created by inference")

            # 3. Upload output to S3
            logger.info("Uploading result to S3...")
            s3.upload_file(local_out, S3_BUCKET, output_key)
            logger.info(f"Uploaded {local_out} to {output_key}")

        result = {
            "status": "success",
            "message": "DEM inpainting completed successfully",
            "bucket": S3_BUCKET,
            "input_key": input_key,
            "output_key": output_key,
            "filename": filename,
        }
        
        logger.info(f"Job completed successfully: {result}")
        return result

    except Exception as e:
        error_msg = f"Error processing {filename if 'filename' in locals() else 'unknown file'}: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            "status": "error",
            "message": error_msg,
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


if __name__ == "__main__":
    logger.info("Starting RunPod serverless handler for DEM inpainting...")
    runpod.serverless.start({"handler": handler})