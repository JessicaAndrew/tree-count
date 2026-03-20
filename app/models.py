""" Data models for the Missing Trees API. """

from pydantic import BaseModel, Field
from typing import Dict, List, Union


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


class HealthResponse(BaseModel):
    """ Health endpoint response. """
    status: str = Field(..., description="Service health status")


class RootResponse(BaseModel):
    """ Root endpoint response with quick links. """
    message: str = Field(..., description="Service name")
    health: str = Field(..., description="Health endpoint path")
    docs: str = Field(..., description="Swagger UI endpoint path")
    missing_trees_example: str = Field(..., description="Example missing-trees endpoint path")


class VisualizationResponse(BaseModel):
    """ Visualisation endpoint response. """
    status: str = Field(..., description="Operation status")
    image_url: str = Field(..., description="Relative URL to the generated PNG file")
    metadata: Dict[str, Union[int, str]] = Field(
        default_factory=dict,
        description="Visualization metadata including orchard_id, survey_id, tree_count, missing_count, output_path",
    )
