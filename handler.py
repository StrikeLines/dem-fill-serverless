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


def run_dem_inpainting(input_path: str, output_dir: str = None) -> str:
    """
    Calls the dem-fill inference command, using the same settings
    as in the original init script.

    Expected behavior:
        - Reads input_path
        - Creates processed file in ./output directory with "_processed.tif" suffix
        - Returns the path to the processed file
    """
    
    logger.info(f"Running DEM inpainting on {input_path}")
    logger.info(f"Input file exists: {os.path.exists(input_path)}")
    logger.info(f"Input directory contents: {os.listdir(os.path.dirname(input_path))}")
    
    # The dem-fill script now standardizes output to ./output directory
    # and appends "_processed" to the filename
    name, ext = os.path.splitext(os.path.basename(input_path))
    expected_output_path = os.path.join("/workspace/shared/dem-fill/output", f"{name}_processed{ext}")
    
    logger.info(f"Expected output path in run_dem_inpainting: {expected_output_path}")
    
    # Command without output_dir_name parameter as it now uses standardized ./output directory
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
        input_path
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
        logger.info(f"stdout: {result.stdout}")
        
        # Check if output directory exists
        output_dir_path = "/workspace/shared/dem-fill/output"
        if os.path.exists(output_dir_path):
            logger.info(f"Output directory contents: {os.listdir(output_dir_path)}")
        else:
            logger.warning(f"Output directory {output_dir_path} does not exist")
        
        return expected_output_path
        
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
        # INPUT_PREFIX and OUTPUT_PREFIX already include trailing slashes from env vars
        input_key = f"{INPUT_PREFIX.rstrip('/')}/{filename}"
        output_key = f"{OUTPUT_PREFIX.rstrip('/')}/{filename}"

        logger.info(f"Processing file: {filename}")
        logger.info(f"Input S3 key: {input_key}")
        logger.info(f"Output S3 key: {output_key}")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up input path
            local_in = os.path.join(tmpdir, filename)  # Keep original filename

            logger.info("Downloading input file from S3...")
            # 1. Download input from S3
            s3.download_file(S3_BUCKET, input_key, local_in)
            logger.info(f"Downloaded {input_key} to {local_in}")
            logger.info(f"Local input file exists: {os.path.exists(local_in)}")

            # 2. Run DEM inpainting
            logger.info("Starting DEM inpainting inference...")
            logger.info(f"Input file path: {local_in}")
            
            # Run inference - output will be in standardized location
            processed_file = run_dem_inpainting(local_in)
            
            # The processed file will be in the standardized output directory
            # with "_processed" appended to the filename
            name, ext = os.path.splitext(filename)
            processed_filename = f"{name}_processed{ext}"
            expected_output_path = f"/workspace/shared/dem-fill/output/{processed_filename}"
            
            logger.info(f"Expected output path: {expected_output_path}")
            
            # Check if output directory exists
            output_dir_path = "/workspace/shared/dem-fill/output"
            if os.path.exists(output_dir_path):
                logger.info(f"Output directory contents: {os.listdir(output_dir_path)}")
            else:
                logger.warning(f"Output directory {output_dir_path} does not exist")

            # Verify output file exists
            if not os.path.exists(expected_output_path):
                raise RuntimeError(f"Expected output file {expected_output_path} was not created by inference")

            # 3. Upload output to S3
            logger.info("Uploading result to S3...")
            # Use processed filename for the output key to indicate it's been processed
            output_key = f"{OUTPUT_PREFIX}{processed_filename}"
            logger.info(f"Uploading from local path: {expected_output_path}")
            logger.info(f"Uploading to S3 bucket: {S3_BUCKET}")
            logger.info(f"Uploading to S3 key: {output_key}")
            s3.upload_file(expected_output_path, S3_BUCKET, output_key)
            logger.info(f"Successfully uploaded {expected_output_path} to s3://{S3_BUCKET}/{output_key}")

        result = {
            "status": "success",
            "message": "DEM inpainting completed successfully",
            "bucket": S3_BUCKET,
            "input_key": input_key,
            "output_key": output_key,
            "input_filename": filename,
            "output_filename": processed_filename,
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