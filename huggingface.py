from huggingface_hub import snapshot_download
import os

# Download to a specific local directory
local_dir = "./models/distilbert-base-uncased"
snapshot_download(
    repo_id="distilbert/distilbert-base-uncased", 
    repo_type="model",
    local_dir=local_dir,
    local_dir_use_symlinks=False  # Creates actual files instead of symlinks
)