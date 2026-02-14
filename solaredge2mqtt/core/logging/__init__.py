import sys

from loguru import logger
from pymodbus import pymodbus_apply_logging_config

from solaredge2mqtt.core.logging.models import LoggingLevelEnum


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    logger.configure(
        handlers=[{"sink": sys.stdout, "level": logging_level.level}]
    )

    # Configure pymodbus with the same logging level
    pymodbus_apply_logging_config(level=logging_level.value)
