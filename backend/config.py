import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class Settings:
    """
    Application settings.
    """
    # API Keys
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "your-youtube-api-key")
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "your-pinecone-api-key")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "your-gemini-api-key")

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Redis/Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./youtube_audit.db")

    # Authentication
    # A simple static token for prototype purposes
    API_BEARER_TOKEN: str = os.getenv("API_BEARER_TOKEN", "a-secure-static-token")


settings = Settings()