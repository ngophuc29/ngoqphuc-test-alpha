import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Gemini Config
# The prompt specifies the Docker env var is API_KEY
API_KEY = os.getenv("API_KEY") or os.getenv("GEMINI_API_KEY")

# Vector Store Config
VECTOR_STORE_NAME = "OptiBot Support Docs"

# Zendesk Scraping Config
ZENDESK_URL = os.getenv("ZENDESK_URL", "https://support.optisigns.com/api/v2/help_center/en-us/articles.json")
ARTICLE_LIMIT = int(os.getenv("ARTICLE_LIMIT", "30"))

# Validate required variables
def validate_config():
    if not API_KEY:
        raise ValueError("API_KEY (or GEMINI_API_KEY) environment variable is required. Please set it in your environment or .env file.")
