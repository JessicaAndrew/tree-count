""" Data models for the Missing Trees API. """

from pydantic import BaseModel, Field
from typing import List


class GpsCoordinate(BaseModel):
    """ GPS coordinate model. """
    lat: float = Field(..., description="Latitude coordinate")
    lng: float = Field(..., description="Longitude coordinate")


class MissingTreesResponse(BaseModel):
    """ Response model for missing trees endpoint. """
    missing_trees: List[GpsCoordinate] = Field(
        default_factory=list, description="List of GPS coordinates of missing trees"
    )


class TreeData(BaseModel):
    """ Tree data from Aerobotics API. """
    lat: float
    lng: float
