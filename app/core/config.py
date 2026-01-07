# =====================================================
# FILE: app/core/config.py
# Application Configuration Settings
# =====================================================
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict, Field  # ⭐ ADD Field HERE
from typing import Optional, List
from dotenv import load_dotenv
from urllib.parse import quote_plus
import os

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "CALIM360"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    BASE_URL: str = Field(default="https://calim360.com")
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]
    
    # Database Configuration
    DB_HOST: str
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DATABASE_URL: Optional[str] = None
    
    # Database Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False
    
    # Security
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # Session Settings
    SESSION_COOKIE_NAME: str = "smrt_clm_session"
    SESSION_EXPIRE_HOURS: int = 24
    
    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Email Configuration
    SMTP_HOST: str = "smtpout.secureserver.net"
    SMTP_PORT: int = 465
    SMTP_USER: Optional[str] = "sales@calim360.com"
    SMTP_PASSWORD: Optional[str] = "Calim@Doha2025%%!"
    EMAILS_FROM_EMAIL: str = "sales@calim360.com"
    FROM_NAME: str ="Calim360"
    
    # File Storage
    UPLOAD_DIR: str = "app/uploads"
    MAX_UPLOAD_SIZE: int = 104857600
    
    # AI Configuration - OpenAI
    # OPENAI_API_KEY: Optional[str] = None
    
    # AI Configuration - Claude/Anthropic (Primary AI Engine)
    # ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None  #  ADD THIS LINE
    CLAUDE_MODEL: str = "claude-opus-4-20250514"
    CLAUDE_MAX_TOKENS: int = 16000  #  ADD THIS LINE
    CLAUDE_TEMPERATURE: float = 0.7  #  ADD THIS LINE
    MAX_TOKENS: int = 8000
    API_TIMEOUT: int = 300


    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_MAX_TOKENS: int = 4000
    
    # Blockchain Configuration
    BLOCKCHAIN_ENABLED: bool = True
    BLOCKCHAIN_NETWORK: str = "hyperledger-fabric"
    
    @field_validator('CLAUDE_API_KEY', mode='before')
    @classmethod
    def set_claude_key(cls, v, values):
        """Use ANTHROPIC_API_KEY if CLAUDE_API_KEY is not set"""
        if not v and 'ANTHROPIC_API_KEY' in values.data:
            return values.data['ANTHROPIC_API_KEY']
        return v
    
    # Pydantic v2 configuration
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    
    @property
    def get_database_url(self) -> str:
        """Construct database URL from components"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"mysql+pymysql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

# Create settings instance
settings = Settings()