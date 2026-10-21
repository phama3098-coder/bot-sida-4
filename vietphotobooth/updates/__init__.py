"""
1998 TEAM — Photobooth Auto-Update System
"""

from .manifest import UpdateManifest
from .updater import UpdateManager, UpdateCheckWorker, UpdateDownloadWorker, check_network_connectivity
from .dialogs import UpdateNotificationDialog, UpdateProgressDialog
from .migration import create_pre_update_backup, verify_user_data_intact, restore_backup

__all__ = [
    "UpdateManifest",
    "UpdateManager",
    "UpdateCheckWorker",
    "UpdateDownloadWorker",
    "UpdateNotificationDialog",
    "UpdateProgressDialog",
    "create_pre_update_backup",
    "verify_user_data_intact",
    "restore_backup",
    "check_network_connectivity",
]
