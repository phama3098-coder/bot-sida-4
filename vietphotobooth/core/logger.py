"""
VietPhotoBooth Logger Module
Centralized logging with file rotation and console output.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_logger = None

def get_logger(log_dir: str = None) -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("VietPhotoBooth")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Clear existing handlers if any
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s.%(module)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler with safe UTF-8 encoding on Windows
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Determine log directory
    if not log_dir:
        base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        log_dir = os.path.join(base_dir, "VietPhotoBooth", "Logs")
    
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "vietphotobooth.log")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        console_handler.setLevel(logging.DEBUG)
        logger.warning(f"Không thể khởi tạo file log tại {log_dir}: {e}")

    _logger = logger
    return logger
