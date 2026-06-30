import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

# Vector Store Config
VECTOR_STORE_NAME = "OptiBot Support Docs"

# Zendesk Scraping Config
ZENDESK_URL = os.getenv("ZENDESK_URL", "https://support.optisigns.com/api/v2/help_center/en-us/articles.json")
ARTICLE_LIMIT = int(os.getenv("ARTICLE_LIMIT", "30"))

# Validate required variables
def validate_config():
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required. Please set it in your environment or .env file.")
