#!/bin/bash

# RunPod Initialization Script for dem-fill project

echo "Starting RunPod initialization..."

# Navigate to shared workspace
cd /workspace/shared

# Clone the repository with authentication
git clone https://StrikeLines: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@github.com/StrikeLines/dem-fill.git

# Navigate into the cloned repository
echo "Entering dem-fill directory..."
cd /workspace/shared/dem-fill

# Download the model from Google Drive
echo "Downloading model from Google Drive..."
mkdir /workspace/shared/dem-fill/pretrained
wget --no-check-certificate 'https://drive.usercontent.google.com/download?id=1bgOoUduXz62M03OxOOV0WK1J7ylsgnYR&export=download&confirm=t&uuid=1c4eb783-6126-4132-9796-f35705b4d482' -O /workspace/shared/dem-fill/pretrained/20.zip
cd /workspace/shared/dem-fill/pretrained
unzip 20.zip /workspace/shared/dem-fill/pretrained/
rm 20.zip


# Install Python requirements
echo "Installing Python requirements..."
cd /workspace/shared/dem-fill/
pip install -r requirements.txt


### END INIT SCRIPT ###


### Inference command in repository ###

 python run.py -p test -c /workspace/shared/dem-fill/config/dem_completion.json \
  --resume_state /workspace/shared/dem-fill/pretrained/20 \
  --n_timestep 100 \
  --input_img "/path/to/input/file.tif" \
  

### Container configuration ###
Run with a 5090 GPU
200 GB of working storage
Pytorch 2.8
The rest of the Python machine learning stack


### S3 Bucket Config ###
S3 Bucket ID: 823878c20ad3fb98020f8b772927ccbb0a0f1ecb986b8595d7c4da045134613b
US East (N. Virginia) us-east-1
Access key: AKIA2YJKTW6TG42NCPBM
Secret Access Key: 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
the "completed" folder is here: s3://dem-fill-serverless-file-store/completed/ 
The "to-process" folder is here s3://dem-fill-serverless-file-store/to-process/


