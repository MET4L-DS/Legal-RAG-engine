# Pre-download the SentenceTransformer model during build
# Cache to a directory that will persist in the deployed container
import os

# Set cache directory BEFORE importing transformers/sentence_transformers
# This ensures the model is saved to a location that persists in the container
os.environ["HF_HOME"] = os.path.join(os.getcwd(), ".hf_cache")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(os.getcwd(), ".hf_cache")

from sentence_transformers import SentenceTransformer

model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
print(f"Pre-downloading model: {model_name}")
print(f"Cache directory: {os.environ['HF_HOME']}")
model = SentenceTransformer(model_name)
print("Model downloaded and cached successfully!")
print(f"Cache contents: {os.listdir(os.environ['HF_HOME'])}")
