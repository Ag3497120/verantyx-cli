import os

from huggingface_hub import HfApi

print("Uploading model_glm.jgen to HuggingFace...")
api = HfApi()
api.upload_file(
    path_or_fileobj="model_glm.jgen",
    path_in_repo="model_glm.jgen",
    repo_id="zai-org/GLM-5.2-JCross-SVD",
    repo_type="model",
    token=os.environ["HF_TOKEN"],
)
print("Upload complete!")
