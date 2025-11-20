# DEM Fill Serverless RunPod Setup

A serverless RunPod implementation for Digital Elevation Model (DEM) inpainting using the [dem-fill](https://github.com/StrikeLines/dem-fill) project. This setup processes GeoTIFF files stored in S3, runs GPU-accelerated inference, and returns completed results with automatic scaling and no idle billing.

## Architecture Overview

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌─────────────┐
│   Client    │───▶│     S3       │───▶│ RunPod Serverless│───▶│     S3      │
│             │    │ (to-process) │    │   (GPU + DEM    │    │ (completed) │
│             │    │              │    │    inpainting)  │    │             │
└─────────────┘    └──────────────┘    └─────────────────┘    └─────────────┘
```

## Features

- **Serverless**: Pay only for GPU compute time used
- **GPU Accelerated**: NVIDIA RTX 5090 for fast inference
- **S3 Integration**: Automatic file handling from input to output buckets
- **Error Handling**: Comprehensive logging and error reporting
- **Scalable**: Automatic scaling based on demand

## Prerequisites

### Required Accounts & Services
- [RunPod](https://runpod.io/) account with API access
- AWS account with S3 access
- Docker for building images
- Container registry (GitHub Container Registry, Docker Hub, etc.)

### Required Software
- Docker
- Python 3.8+ (for client script)
- Git

### AWS S3 Setup

Your S3 bucket should be configured with these folders:
- `s3://dem-fill-serverless-file-store/to-process/` (input files)
- `s3://dem-fill-serverless-file-store/completed/` (output files)

**IAM Policy Required:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::dem-fill-serverless-file-store"
    },
    {
      "Sid": "AllowReadToProcess",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::dem-fill-serverless-file-store/to-process/*"
    },
    {
      "Sid": "AllowWriteCompleted",
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::dem-fill-serverless-file-store/completed/*"
    },
    {
      "Sid": "AllowReadCompleted",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::dem-fill-serverless-file-store/completed/*"
    }
  ]
}
```

## Setup Instructions

### Step 1: Clone This Repository

```bash
git clone <this-repository>
cd dem-fill-serverless
```

### Step 2: Build Docker Image

#### Option A: Public Repository (Recommended)
If the dem-fill repository is public:

```bash
docker build -t dem-fill-serverless:latest .
```

#### Option B: Private Repository
If using a private repository, you need a GitHub token:

```bash
docker build \
  --build-arg GITHUB_TOKEN=your_github_token_here \
  -t dem-fill-serverless:latest .
```

### Step 3: Push to Container Registry

#### GitHub Container Registry
```bash
# Login to GHCR
echo $GITHUB_PAT | docker login ghcr.io -u your_github_username --password-stdin

# Tag and push
docker tag dem-fill-serverless:latest ghcr.io/your_github_username/dem-fill-serverless:latest
docker push ghcr.io/your_github_username/dem-fill-serverless:latest
```

#### Docker Hub
```bash
# Login to Docker Hub

# docker login command
# docker push travisgriggs304/runpod-serverless:tagname

docker login

# Tag and push
docker tag dem-fill-serverless:latest your_dockerhub_username/dem-fill-serverless:latest
docker push your_dockerhub_username/dem-fill-serverless:latest
```

### Step 4: Create RunPod Serverless Endpoint

1. Go to [RunPod Console](https://runpod.io/console/serverless)
2. Click "Create Endpoint"
3. Configure the endpoint:

**Basic Settings:**
- **Name**: `dem-fill-serverless`
- **Image**: `ghcr.io/your_username/dem-fill-serverless:latest` (or your registry)

**Hardware:**
- **GPU Type**: NVIDIA RTX 5090 (or best available)
- **Container Disk**: 200 GB
- **vCPU/RAM**: Default (will be set automatically based on GPU)

**Environment Variables:**
```bash
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-1
DEM_S3_BUCKET=dem-fill-serverless-file-store
DEM_INPUT_PREFIX=to-process/
DEM_OUTPUT_PREFIX=completed/
```

**Advanced Settings:**
- **Max Workers**: 3-5 (adjust based on needs)
- **Idle Timeout**: 5 seconds (for cost efficiency)
- **Request Timeout**: 3600 seconds (1 hour for large files)

4. Click "Create Endpoint"
5. Note your endpoint ID (format: `xxxxxxxxxx`)

### Step 5: Test the Setup

#### Install Client Dependencies
```bash
pip install boto3 requests
```

#### Set Environment Variables
```bash
export RUNPOD_API_KEY=your_runpod_api_key
export RUNPOD_ENDPOINT_ID=your_endpoint_id
export AWS_ACCESS_KEY_ID=your_aws_access_key
export AWS_SECRET_ACCESS_KEY=your_aws_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

#### Run Test
```bash
python client_example.py path/to/your/dem_file.tif --filename test_tile.tif
```

## Usage

### Basic Usage
```bash
python client_example.py input_dem.tif --filename my_tile.tif
```

### Advanced Usage
```bash
# Custom timeout and polling interval
python client_example.py input_dem.tif \
  --filename large_tile.tif \
  --timeout 7200 \
  --poll-interval 30

# Process file already in S3
python client_example.py dummy_path.tif \
  --filename existing_file.tif \
  --skip-upload
```

### Direct API Call
```bash
curl -X POST \
  https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "filename": "test_tile.tif"
    }
  }'
```

## File Structure

```
dem-fill-serverless/
├── Dockerfile              # Container image definition
├── handler.py              # RunPod serverless handler
├── client_example.py       # Example client for testing
├── README.md               # This documentation
├── Runpod_docker.txt       # Original Docker setup notes
├── runpod_init.sh          # Original initialization script
└── runpod_serverless_prompt.txt  # Original requirements
```

## Expected Input/Output

**Input**: GeoTIFF files with missing/corrupted elevation data
**Output**: GeoTIFF files with inpainted elevation data using deep learning

**Supported formats**: 
- GeoTIFF (.tif, .tiff)
- Single-band elevation data
- Geographic or projected coordinate systems

## Monitoring and Logs

### RunPod Console
- View job status and logs in the RunPod console
- Monitor endpoint usage and performance
- Check error logs for debugging

### Client Script Logs
The client script provides detailed progress information:
```
=== DEM Fill Serverless Client ===
Input file: test_dem.tif
S3 filename: test_dem.tif
RunPod endpoint: xxxxxxxxxx

✓ Upload successful
✓ Job triggered successfully
Job ID: xxxxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Job status: IN_PROGRESS (elapsed: 30s)
Job status: IN_PROGRESS (elapsed: 60s)
✓ Job completed successfully!

=== Final Result ===
{
  "status": "success",
  "message": "DEM inpainting completed successfully",
  "bucket": "dem-fill-serverless-file-store",
  "input_key": "to-process/test_dem.tif",
  "output_key": "completed/test_dem.tif",
  "filename": "test_dem.tif"
}

✓ Completed file should be at: s3://dem-fill-serverless-file-store/completed/test_dem.tif
✓ Output file confirmed to exist in S3
```

## Troubleshooting

### Common Issues

#### 1. Docker Build Failures
```bash
# Clear Docker cache and rebuild
docker system prune -a
docker build --no-cache -t dem-fill-serverless:latest .
```

#### 2. S3 Permission Errors
- Verify IAM policy is correctly applied
- Check AWS credentials are valid
- Ensure bucket exists and is accessible

#### 3. RunPod Endpoint Issues
- Check endpoint status in RunPod console
- Verify environment variables are set correctly
- Review container logs for errors

#### 4. Job Timeouts
- Increase timeout in client script
- Check GPU availability and queue times
- Consider splitting large files

#### 5. Memory Issues
- Ensure sufficient container disk space (200GB+)
- Monitor GPU memory usage
- Process smaller tiles if necessary

### Debug Commands

```bash
# Test S3 access
aws s3 ls s3://dem-fill-serverless-file-store/ --recursive

# Test Docker image locally
docker run -it --rm dem-fill-serverless:latest /bin/bash

# Check RunPod endpoint status
curl -H "Authorization: Bearer $RUNPOD_API_KEY" \
     https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID
```

## Security Considerations

1. **Never commit secrets to Git**:
   - Use environment variables for all credentials
   - Add `.env` files to `.gitignore`
   - Rotate compromised credentials immediately

2. **Use least-privilege IAM policies**:
   - Limit S3 access to required buckets only
   - Use separate IAM users for different environments

3. **Secure container registry**:
   - Use private registries for production
   - Enable vulnerability scanning
   - Keep base images updated

## Cost Optimization

1. **Idle Timeout**: Set to 5 seconds to minimize idle billing
2. **GPU Selection**: Use appropriate GPU for your workload size
3. **Batch Processing**: Process multiple files in sequence when possible
4. **Monitoring**: Track usage patterns and optimize accordingly

## Performance Tuning

1. **Container Disk**: Ensure sufficient space for large files (200GB+)
2. **Request Timeout**: Set appropriate timeouts for your file sizes
3. **Max Workers**: Balance between parallel processing and cost
4. **GPU Memory**: Monitor usage and optimize model parameters

## Support

For issues related to:
- **dem-fill algorithm**: Check the [original repository](https://github.com/StrikeLines/dem-fill)
- **RunPod platform**: Contact RunPod support
- **This implementation**: Create an issue in this repository

## License

This implementation follows the same license as the original dem-fill project. Check the upstream repository for license details.