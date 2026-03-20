""" Configuration settings for the application. """

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """ Application settings. """
    app_name: str = "Aerobotics Missing Trees API"
    app_version: str = "1.0.0"
    api_base_url: str = "https://api.aerobotics.com"
    api_key: Optional[str] = None
    environment: str = "development"
    debug: bool = False

    class Config:
        """ Pydantic settings configuration. """
        env_file = ".env"
        case_sensitive = False


settings = Settings()
