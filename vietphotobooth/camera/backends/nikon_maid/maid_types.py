"""
1998 TEAM — Photobooth Nikon MAID3 SDK ctypes Types & Constants
Type definitions, structure layouts with pack=2 alignment, enums and callback prototypes
for Nikon Type0026 (Nikon D780) Modular Acquisition Interface Definition (MAID).
"""

import ctypes
from enum import IntEnum

# ==============================================================================
# ENUMS
# ==============================================================================

class NkMAIDObjectType(IntEnum):
    MODULE = 1
    SOURCE = 2
    ITEM = 3
    DATA = 4

class NkMAIDCommand(IntEnum):
    ASYNC = 0
    OPEN = 1
    CLOSE = 2
    GET_CAP_COUNT = 3
    GET_CAP_INFO = 4
    CAP_START = 5
    CAP_SET = 6
    CAP_GET = 7
    CAP_GET_DEFAULT = 8
    CAP_GET_ARRAY = 9
    MARK = 10
    ABORT_TO_MARK = 11
    ABORT = 12
    ENUM_CHILDREN = 13
    GET_PARENT = 14
    RESET_TO_DEFAULT = 15

class NkMAIDDataType(IntEnum):
    NULL = 0
    BOOLEAN = 1
    INTEGER = 2
    UNSIGNED = 3
    BOOLEAN_PTR = 4
    INTEGER_PTR = 5
    UNSIGNED_PTR = 6
    FLOAT_PTR = 7
    POINT_PTR = 8
    SIZE_PTR = 9
    RECT_PTR = 10
    STRING_PTR = 11
    DATETIME_PTR = 12
    CALLBACK_PTR = 13
    RANGE_PTR = 14
    ARRAY_PTR = 15
    ENUM_PTR = 16
    OBJECT_PTR = 17
    CAPINFO_PTR = 18
    GENERIC_PTR = 19

class NkMAIDCapType(IntEnum):
    PROCESS = 0
    BOOLEAN = 1
    INTEGER = 2
    UNSIGNED = 3
    FLOAT = 4
    POINT = 5
    SIZE = 6
    RECT = 7
    STRING = 8
    DATETIME = 9
    CALLBACK = 10
    ARRAY = 11
    ENUM = 12
    RANGE = 13
    GENERIC = 14

class NkMAIDCapOperations(IntEnum):
    START = 0x0001
    GET = 0x0002
    SET = 0x0004
    GET_ARRAY = 0x0008
    GET_DEFAULT = 0x0010

class NkMAIDEvent(IntEnum):
    ADD_CHILD = 0
    REMOVE_CHILD = 1
    WARMING_UP = 2
    WARMED_UP = 3
    CAP_CHANGE = 4
    ORPHANED_CHILDREN = 5
    CAP_CHANGE_VALUE_ONLY = 6
    ADD_PREVIEW_IMAGE = 263
    CAPTURE_COMPLETE = 264
    ADD_CHILD_IN_CARD = 265
    RECORDING_INTERRUPTED = 266
    CAP_CHANGE_OPERATION_ONLY = 267
    FIRST_CAPTURE_COMPLETE = 268

class NkMAIDCapability(IntEnum):
    # Standard MAID3 capabilities
    ASYNC_RATE = 1
    PROGRESS_PROC = 2
    EVENT_PROC = 3
    DATA_PROC = 4
    UI_REQUEST_PROC = 5
    IS_ALIVE = 6
    CHILDREN = 7
    STATE = 8
    NAME = 9
    DESCRIPTION = 10
    INTERFACE = 11
    DATA_TYPES = 12
    DATE_TIME = 13
    STORED_BYTES = 14
    EJECT = 15
    FEED = 16
    CAPTURE = 17
    MEDIA_PRESENT = 18
    MODE = 19
    ACQUIRE = 20
    AUTOFOCUS = 29
    BATTERY_LEVEL = 0x0031

    # Nikon Vendor Capabilities (Type0026 / D780)
    VENDOR_BASE = 0x8000
    VENDOR_BASE_DX2 = 0x8100
    MODULE_MODE = 0x8101
    LOCK_FOCUS = 0x8105
    COMPRESSION_LEVEL = 0x8110
    FOCUS_MODE = 0x8120
    SHUTTER_SPEED = 0x8112
    APERTURE = 0x8113
    ISO_CONTROL = 0x816C
    AF_MODE = 0x81C3
    LIVE_VIEW_STATUS = 0x823E
    CONTRAST_AF = 0x8240
    GET_LIVE_VIEW_IMAGE = 0x8247
    CONTRAST_AF_AREA = 0x824A
    LIVE_VIEW_PROHIBIT = 0x825E
    LIVE_VIEW_AF = 0x8275
    SAVE_MEDIA = 0x8305
    AF_MODE_AT_LIVE_VIEW = 0x8310
    TERMINATE_CAPTURE = 0x8318
    LIVE_VIEW_EXPOSURE_PREVIEW = 0x8333
    LIVE_VIEW_SELECTOR = 0x8334
    LIVE_VIEW_IMAGE_SIZE = 0x8353
    AF_CAPTURE_LV = 0x849A
    CAPTURE_ASYNC = 0x84D8
    AF_CAPTURE_ASYNC = 0x84D9
    LIVE_VIEW_IMAGE_STATUS = 0x8517
    LIVE_VIEW_ZOOM_AREA = 0x8518

class NkMAIDLiveViewStatus(IntEnum):
    OFF = 0
    ON = 1
    ON_MENU = 2
    ON_REMOTE_LV = 3
    ON_CAMERA_LV = 4

class NkMAIDLiveViewImageSize(IntEnum):
    QVGA = 1  # 320 x 213 (3:2)
    VGA = 2   # 640 x 424 (3:2)
    XGA = 3   # 1024 x 680 (3:2)

class NkMAIDLiveViewImageStatus(IntEnum):
    CANNOT_ACQUIRE = 0
    CAN_ACQUIRE = 1

class NkMAIDSaveMedia(IntEnum):
    CARD = 0
    SDRAM = 1
    CARD_SDRAM = 2

class NkMAIDContrastAF(IntEnum):
    START = 0x00
    STOP = 0x01
    OK = 0x10
    OUT_OF_FOCUS = 0x11
    BUSY = 0x12

class NkMAIDLiveViewAF(IntEnum):
    FACE = 0
    WIDE = 1
    NORMAL = 2
    SUBJECT_TRACKING = 3
    SPOT = 4

class NkMAIDAFModeAtLiveView(IntEnum):
    AF_S = 0
    AF_C = 1
    AF_F = 2
    MF_FIX = 3
    MF_SEL = 4
    AF_A = 5

class NkMAIDResult(IntEnum):
    # Success
    NO_ERROR = 0
    PENDING = 1
    WAITING_2ND_RELEASE = 168

    # Errors
    NOT_SUPPORTED = -127
    UNEXPECTED_DATA_TYPE = -126
    VALUE_OUT_OF_BOUNDS = -125
    BUFFER_SIZE = -124
    ABORTED = -123
    NO_MEDIA = -122
    NO_EVENT_PROC = -121
    NO_DATA_PROC = -120
    ZOMBIE_OBJECT = -119
    OUT_OF_MEMORY = -118
    UNEXPECTED_ERROR = -117
    HARDWARE_ERROR = -116
    MISSING_COMPONENT = -115

    OUT_OF_FOCUS = 137
    BATTERY_EXHAUSTED = 147
    CAPTURE_FAILURE = 148
    DEVICE_BUSY = 152

# ==============================================================================
# CTYPES STRUCTURES (All aligned with _pack_ = 2)
# ==============================================================================

class NkMAIDPoint(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("x", ctypes.c_int32),
        ("y", ctypes.c_int32),
    ]

class NkMAIDObject(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulID", ctypes.c_uint32),
        ("refClient", ctypes.c_void_p),
        ("refModule", ctypes.c_void_p),
    ]

class NkMAIDCallback(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("pProc", ctypes.c_void_p),
        ("refProc", ctypes.c_void_p),
    ]

class NkMAIDCapInfo(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("ulID", ctypes.c_uint32),
        ("ulType", ctypes.c_uint32),
        ("ulVisibility", ctypes.c_uint32),
        ("ulOperations", ctypes.c_uint32),
        ("szDescription", ctypes.c_char * 256),
    ]

class NkMAIDString(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("str", ctypes.c_char * 256),
    ]

class NkMAIDArray(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulElements", ctypes.c_uint32),
        ("ulDimSize1", ctypes.c_uint32),
        ("ulDimSize2", ctypes.c_uint32),
        ("ulDimSize3", ctypes.c_uint32),
        ("wPhysicalBytes", ctypes.c_uint16),
        ("wLogicalBits", ctypes.c_uint16),
        ("pData", ctypes.c_void_p),
    ]

class NkMAIDEnum(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulElements", ctypes.c_uint32),
        ("ulValue", ctypes.c_uint32),
        ("ulDefault", ctypes.c_uint32),
        ("wPhysicalBytes", ctypes.c_int16),
        ("pData", ctypes.c_void_p),
    ]

class NkMAIDRange(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("lfValue", ctypes.c_double),
        ("lfDefault", ctypes.c_double),
        ("ulValueIndex", ctypes.c_uint32),
        ("ulDefaultIndex", ctypes.c_uint32),
        ("lfLower", ctypes.c_double),
        ("lfUpper", ctypes.c_double),
        ("ulSteps", ctypes.c_uint32),
    ]

class NkMAIDFileInfo(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulFileDataType", ctypes.c_uint32),
        ("ulTotalLength", ctypes.c_uint32),
        ("ulStart", ctypes.c_uint32),
        ("ulLength", ctypes.c_uint32),
        ("fDiskFile", ctypes.c_uint32),
        ("fRemoveObject", ctypes.c_uint32),
    ]

# ==============================================================================
# CALLBACK FUNCTION SIGNATURES (WINFUNCTYPE for Win64 standard calling convention)
# ==============================================================================

MAIDEntryPointProc = ctypes.WINFUNCTYPE(
    ctypes.c_int32,     # NKERROR return
    ctypes.c_void_p,    # pObject
    ctypes.c_uint32,    # ulCommand
    ctypes.c_uint32,    # ulParam
    ctypes.c_uint32,    # ulDataType
    ctypes.c_uint64,    # data (NKPARAM on 64-bit)
    ctypes.c_void_p,    # pfnComplete
    ctypes.c_void_p     # refComplete
)

MAIDCompletionProc = ctypes.WINFUNCTYPE(
    None,
    ctypes.c_void_p,    # pObject
    ctypes.c_uint32,    # ulCommand
    ctypes.c_uint32,    # ulParam
    ctypes.c_uint32,    # ulDataType
    ctypes.c_uint64,    # data
    ctypes.c_void_p,    # refComplete
    ctypes.c_int32      # nResult (NKERROR)
)

MAIDEventProc = ctypes.WINFUNCTYPE(
    None,
    ctypes.c_void_p,    # refClient
    ctypes.c_uint32,    # ulEvent
    ctypes.c_uint64     # data (NKPARAM)
)

MAIDDataProc = ctypes.WINFUNCTYPE(
    ctypes.c_int32,     # NKERROR return
    ctypes.c_void_p,    # refClient
    ctypes.c_void_p,    # pDataInfo
    ctypes.c_void_p     # pData
)

MAIDProgressProc = ctypes.WINFUNCTYPE(
    None,
    ctypes.c_uint32,    # ulCommand
    ctypes.c_uint32,    # ulParam
    ctypes.c_void_p,    # refComplete
    ctypes.c_uint32,    # ulDone
    ctypes.c_uint32     # ulTotal
)

MAIDUIRequestProc = ctypes.WINFUNCTYPE(
    ctypes.c_uint32,
    ctypes.c_void_p,    # refProc
    ctypes.c_void_p     # pUIRequest
)
