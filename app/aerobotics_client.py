""" Client for interacting with Aerobotics API. """

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class AeroboticsClient:
    """ Client to interact with Aerobotics API. """

    def __init__(self, api_key: Optional[str] = None):
        """ Initialise the Aerobotics client.

            Args:
                api_key: API key for authentication. Uses settings.api_key if not provided.
        """
        self.api_key = api_key or settings.api_key
        self.base_url = settings.api_base_url

        if not self.api_key:
            raise ValueError("API_KEY is not configured. Set API_KEY in your environment or .env file.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_list(payload: Any) -> List[Dict[str, Any]]:
        """Extract list-like records from common API response envelopes."""
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ("results", "data", "items"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        return []

    def get_orchard(self, orchard_id: int) -> Dict[str, Any]:
        """ Fetch orchard details.

            Args:
                orchard_id: The ID of the orchard.

            Returns:
                Orchard data including polygon boundary and properties.

            Raises:
                requests.HTTPError: If API call fails.
        """
        url = f"{self.base_url}/farming/orchards/{orchard_id}/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        payload = response.json()
        if isinstance(payload, dict):
            return payload

        return {}

    def get_surveys(self, orchard_id: int) -> List[Dict[str, Any]]:
        """ Fetch surveys for an orchard.

            Args:
                orchard_id: The ID of the orchard.

            Returns:
                List of survey records for the orchard.

            Raises:
                requests.HTTPError: If API call fails.
        """
        url = f"{self.base_url}/farming/surveys/?orchard_id={orchard_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return self._extract_list(response.json())

    def get_latest_survey(self, orchard_id: int) -> Optional[Dict[str, Any]]:
        """ Fetch the latest survey for an orchard.

            Args:
                orchard_id: The ID of the orchard.

            Returns:
                The latest survey record, or None if no surveys exist.

            Raises:
                requests.HTTPError: If API call fails.
        """
        surveys = self.get_surveys(orchard_id)

        if not surveys:
            return None

        return max(
            surveys,
            key=lambda survey: date.fromisoformat(survey.get("date", "1900-01-01")),
        )

    def get_tree_surveys(self, survey_id: int) -> List[Dict[str, Any]]:
        """Fetch tree survey point records for a specific survey.

            Args:
                survey_id: The ID of the survey.

            Returns:
                List of tree detections for the survey.

            Raises:
                requests.HTTPError: If API call fails.
        """
        url = f"{self.base_url}/farming/surveys/{survey_id}/tree_surveys/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return self._extract_list(response.json())
