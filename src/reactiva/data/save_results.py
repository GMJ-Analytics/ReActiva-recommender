import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Import project configuration and logger
from reactiva.config import AWS_REGION, S3_BUCKET, LAMBDA_LOG
from reactiva.utils.logger import log_event, setup_logger


# ============================================================
# LOGGER
# ============================================================

logger = setup_logger(
    name="reactiva.data.save_results",
    log_dir=LAMBDA_LOG,
)


# ============================================================
# LOCAL PATHS
# ============================================================

# Project root: ReActiva-recommender/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Local artifacts directory
LOCAL_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "metrics"


# ============================================================
# S3 CONFIGURATION
# ============================================================

S3_RESULTS_PREFIX = "results/predictions"


# ============================================================
# RUN ID
# ============================================================

def generate_run_id() -> str:
    """
    Generates a unique run ID based on date/time and a short UUID hash.
    Avoids accidental overwrites locally and in S3.
    """

    timestamp = datetime.now().strftime("%Y/%m/%d_%H:%M:%S")
    short_hash = uuid.uuid4().hex[:6]

    return f"run_{timestamp}_{short_hash}"


# ============================================================
# LOCAL SAVE
# ============================================================

def save_to_local(
    data,
    file_path: Path,
    is_dataframe: bool = False,
) -> None:
    """
    Saves a DataFrame as CSV or a dictionary as JSON
    to the local filesystem.
    """

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if is_dataframe and isinstance(data, pd.DataFrame):

        data.to_csv(
            file_path,
            index=False,
        )

    else:

        with open(
            file_path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
            )

    log_event(
        logger,
        "Archivo guardado en almacenamiento local",
        path=str(file_path),
        is_dataframe=is_dataframe,
    )


# ============================================================
# S3 UPLOAD
# ============================================================

def upload_to_s3(
    local_path: Path,
    s3_key: str,
    bucket_name: str = S3_BUCKET,
) -> None:
    """
    Uploads a local file to Amazon S3.
    """

    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
    )

    try:

        s3_client.upload_file(
            str(local_path),
            bucket_name,
            s3_key,
        )

        log_event(
            logger,
            "Archivo subido exitosamente a Amazon S3",
            bucket=bucket_name,
            s3_key=s3_key,
            local_path=str(local_path),
        )

    except (BotoCoreError, ClientError) as e:

        log_event(
            logger,
            "Error al intentar subir archivo a Amazon S3",
            level=30,
            bucket=bucket_name,
            s3_key=s3_key,
            error=str(e),
        )

        raise


# ============================================================
# MAIN SAVE FUNCTION
# ============================================================

def save_experiment_results(
    predictions_df: pd.DataFrame,
    metrics_dict: dict,
    metadata_dict: dict = None,
    env: str = None,
) -> str:
    """
    Orchestrates saving predictions, metrics and metadata.

    - Saves a local copy inside artifacts/metrics/<run_id>/.
    - If env == 'prod' or APP_ENV == 'prod',
      uploads the results to Amazon S3.
    """

    current_env = (
        env
        or os.getenv("APP_ENV", "dev")
    ).lower()

    run_id = generate_run_id()

    log_event(
        logger,
        "Iniciando proceso de guardado de resultados",
        run_id=run_id,
        environment=current_env,
    )

    # --------------------------------------------------------
    # Local paths
    # --------------------------------------------------------

    run_local_dir = (
        LOCAL_ARTIFACTS_DIR / run_id
    )

    pred_local_path = (
        run_local_dir / "predictions.csv"
    )

    metrics_local_path = (
        run_local_dir / "metrics.json"
    )

    metadata_local_path = (
        run_local_dir / "metadata.json"
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    full_metadata = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "environment": current_env,
        **(metadata_dict or {}),
    }

    # --------------------------------------------------------
    # Save locally
    # --------------------------------------------------------

    save_to_local(
        predictions_df,
        pred_local_path,
        is_dataframe=True,
    )

    save_to_local(
        metrics_dict,
        metrics_local_path,
    )

    save_to_local(
        full_metadata,
        metadata_local_path,
    )

    # --------------------------------------------------------
    # Upload to S3 in production
    # --------------------------------------------------------

    if current_env == "prod":

        s3_run_prefix = (
            f"{S3_RESULTS_PREFIX}/{run_id}"
        )

        upload_to_s3(
            pred_local_path,
            f"{s3_run_prefix}/predictions.csv",
        )

        upload_to_s3(
            metrics_local_path,
            f"{s3_run_prefix}/metrics.json",
        )

        upload_to_s3(
            metadata_local_path,
            f"{s3_run_prefix}/metadata.json",
        )

    # --------------------------------------------------------
    # Completion log
    # --------------------------------------------------------

    log_event(
        logger,
        "Proceso de guardado completado con éxito",
        run_id=run_id,
    )

    return run_id
