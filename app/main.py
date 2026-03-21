""" Main FastAPI application for Aerobotics Missing Trees API. """

import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.models import (HealthResponse, MissingTreesResponse, RootResponse, VisualizationResponse,)
from app.aerobotics_client import AeroboticsClient
from app.missing_trees import MissingTreesDetector
from app.visualization import build_orchard_visualization


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API to detect missing trees in orchards using Aerobotics data",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

outputs_dir = Path("outputs")
outputs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")


def _extract_tree_coordinate(tree: dict) -> tuple[float, float] | None:
    """ Extract (lat, lng) from common tree payload variants. """
    lat = tree.get("lat", tree.get("latitude"))
    lng = tree.get("lng", tree.get("longitude"))

    if lat is None or lng is None:
        return None

    return float(lat), float(lng)


@app.get("/health", tags=["Health"])
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Returns service health status.",
)
async def health_check() -> HealthResponse:
    """ Health check endpoint. """
    return HealthResponse(status="healthy")


@app.get(
    "/",
    response_model=RootResponse,
    tags=["Health"],
    summary="Service information",
    description="Returns quick links to key API endpoints.",
)
async def root() -> RootResponse:
    """ Root endpoint with quick usage guidance. """
    return RootResponse(
        message="Aerobotics Missing Trees API",
        health="/health",
        docs="/docs",
        missing_trees_example="/orchards/216269/missing-trees",
    )


@app.get(
    "/orchards/{orchard_id}/missing-trees",
    response_model=MissingTreesResponse,
    tags=["Orchards"],
    summary="Get missing trees for an orchard",
    description="Returns GPS coordinates of trees inferred to be missing from the latest survey for the orchard.",
    responses={
        200: {
            "description": "Missing tree coordinates generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "missing_trees": [
                            {"lat": -32.328886, "lng": 18.825847},
                            {"lat": -32.328788, "lng": 18.826424},
                        ]
                    }
                }
            },
        },
        404: {"description": "No surveys found for the given orchard"},
        500: {"description": "Failed to fetch upstream data or compute missing trees"},
    },
)
async def get_missing_trees(orchard_id: int) -> MissingTreesResponse:
    """ Get missing trees for a specific orchard.

        Args:
            orchard_id: The ID of the orchard to analyze

        Returns:
            MissingTreesResponse containing list of missing tree GPS coordinates

        Raises:
            HTTPException: If orchard not found or API call fails
    """
    try:
        # Initialise Aerobotics client
        client = AeroboticsClient()

        # Fetch orchard details
        logger.info(f"Fetching orchard {orchard_id} details")
        orchard = client.get_orchard(orchard_id)

        # Get the latest survey
        logger.info(f"Fetching latest survey for orchard {orchard_id}")
        latest_survey = client.get_latest_survey(orchard_id)

        if not latest_survey:
            raise HTTPException(
                status_code=404,
                detail=f"No surveys found for orchard {orchard_id}",
            )

        survey_id = latest_survey["id"]

        # Get tree surveys
        logger.info(f"Fetching tree surveys for survey {survey_id}")
        tree_surveys = client.get_tree_surveys(survey_id)

        # Extract detected tree coordinates
        detected_trees = []
        for tree in tree_surveys:
            coordinate = _extract_tree_coordinate(tree)
            if coordinate is not None:
                detected_trees.append(coordinate)

        logger.info(f"Found {len(detected_trees)} trees in survey {survey_id}")

        # Extract orchard polygon (supports irregular boundaries)
        orchard_polygon = orchard.get("polygon")
        if not orchard_polygon:
            logger.warning(f"No polygon data for orchard {orchard_id}, cannot compute missing trees")
            return MissingTreesResponse(missing_trees=[])

        # Detect missing trees using polygon boundary
        missing_trees = MissingTreesDetector.detect_missing_trees(
            orchard_polygon=orchard_polygon,
            detected_trees=detected_trees,
        )

        logger.info(f"Detected {len(missing_trees)} missing trees")

        return MissingTreesResponse(missing_trees=missing_trees)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing orchard {orchard_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process orchard: {str(e)}",
        )


@app.get(
    "/orchards/{orchard_id}/visualization",
    response_model=VisualizationResponse,
    tags=["Orchards"],
    summary="Generate orchard visualization",
    description="Generates a PNG showing orchard boundary, detected trees (blue), and missing trees (red).",
    responses={
        200: {
            "description": "Visualization PNG generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "image_url": "/outputs/orchard-216269.png",
                        "metadata": {
                            "orchard_id": 216269,
                            "survey_id": 123456,
                            "tree_count": 102,
                            "missing_count": 5,
                            "output_path": "outputs/orchard-216269.png",
                        },
                    }
                }
            },
        },
        500: {"description": "Failed to generate visualization"},
    },
)
async def generate_orchard_visualization(orchard_id: int) -> VisualizationResponse:
    """ Generate and expose a visualization PNG for an orchard. """
    try:
        output_file = outputs_dir / f"orchard-{orchard_id}.png"
        metadata = build_orchard_visualization(orchard_id=orchard_id, output=output_file)
        return VisualizationResponse(
            status="ok",
            image_url=f"/outputs/{output_file.name}",
            metadata=metadata,
        )
    except Exception as e:
        logger.error(f"Visualization failed for orchard {orchard_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate visualization: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
