"""
1998 TEAM — Photobooth Auto-Update System
"""

from .manifest import UpdateManifest
from .updater import (
    UpdateManager, UpdateCheckWorker, UpdateDownloadWorker,
    check_network_connectivity, verify_digital_signature,
    validate_pe_executable, validate_installer_package,
    generate_updater_runner_script
)
from .dialogs import UpdateNotificationDialog, UpdateProgressDialog, UpdateResultDialog
from .migration import create_pre_update_backup, verify_user_data_intact, restore_backup

__all__ = [
    "UpdateManifest",
    "UpdateManager",
    "UpdateCheckWorker",
    "UpdateDownloadWorker",
    "UpdateNotificationDialog",
    "UpdateProgressDialog",
    "UpdateResultDialog",
    "create_pre_update_backup",
    "verify_user_data_intact",
    "restore_backup",
    "check_network_connectivity",
    "verify_digital_signature",
    "validate_pe_executable",
    "validate_installer_package",
    "generate_updater_runner_script",
]
