import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any


# Palabras que permiten detectar campos potencialmente sensibles.
# Si alguna aparece en el nombre de una variable, su valor no se escribe
# en los logs.
SENSITIVE_WORDS = {
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
    "credential",
}


def _sanitize_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Oculta valores potencialmente sensibles antes de escribirlos en el log.

    Ejemplo:
        {"api_key": "abc123"} -> {"api_key": "[REDACTED]"}
    """
    sanitized = {}

    for key, value in data.items():
        key_lower = key.lower()

        if any(word in key_lower for word in SENSITIVE_WORDS):
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value

    return sanitized


class StructuredFormatter(logging.Formatter):
    """
    Convierte cada registro en una línea JSON.

    Esto permite que los logs sean legibles por personas y también
    procesables posteriormente por herramientas de monitoreo o BI.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        structured_data = getattr(record, "structured_data", None)

        if structured_data:
            log_entry["data"] = _sanitize_data(structured_data)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            log_entry,
            ensure_ascii=False,
            default=str,
        )


def setup_logger(
    name: str = "reactiva",
    log_dir: str | None = None,
    level: int = logging.INFO,
) -> logging.Logger:

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    if log_dir is None:
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            log_dir = "/tmp"
        else:
            log_dir = "artifacts/logs"

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)


    safe_name = name.replace(".", "_")

    log_file = log_path / (
    f"{safe_name}_{datetime.now().strftime('%Y-%m-%d')}.log"
)

    formatter = StructuredFormatter()

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.propagate = False

    return logger


def log_event(
    logger: logging.Logger,
    message: str,
    level: int = logging.INFO,
    **data: Any,
) -> None:
    """-
    Registra un evento estructurado junto con información adicional.

    Ejemplos de uso:
        log_event(logger, "Pipeline iniciado", version="v0.2.0")
        log_event(logger, "Validación completada", rows=10000)
        log_event(logger, "Archivo generado", output_path="data/output.csv")
    """

    logger.log(
        level,
        message,
        extra={
            "structured_data": data,
        },
    )
