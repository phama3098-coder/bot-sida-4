# 1998 TEAM Photobooth — Baseline System Audit

**Audit date:** 2026-11-04 (Asia/Saigon)  
**Repository:** `C:\Users\Admin\Documents\photobooth`  
**Branch:** `feature/v2.0.0-photobooth`  
**Source version:** 2.0.0, Build 206, channel RC; `vietphotobooth/version.py` records release date 2026-11-03.  
**Method:** Read-only static inspection of the current working tree. No tests, application, device, server, printer, or build were run.

## 1. Executive Summary

Photobooth is a Windows native PySide6/Qt desktop application with an optional LAN FastAPI/uvicorn service. The application has modules for camera backends, local events/storage, frames, image processing, filters/beauty, printing, QR sharing, cloud sync, updates, and operator/kiosk UI. Code supports Simulator, DirectShow webcam, digiCamControl, and Nikon MAID3/D780 integrations.

The working tree is not pristine: initial Git status showed 18 modified tracked paths and untracked Spec Kit/skill material plus two tests. This report describes the code as inspected, including those working-tree changes; it does not claim those changes are committed or assign their author. No existing changes were altered.

Key source-level risks:

1. Desktop Kiosk capture calls the camera synchronously from its countdown flow. Nikon and digiCamControl capture methods poll, wait, and transfer data, so the UI can be blocked for seconds. This is a code-path risk; no runtime freeze was measured.
2. Nikon shutter callback runs when MAID `CAP_START` returns an accepted/special result. That does not prove physical shutter timing. In Mirror-Up/two-step release, `WAITING_2ND_RELEASE` can invoke the callback before the second release command.
3. The LAN server binds `0.0.0.0` by default. `/api/config` returns the whole configuration object; settings include a Google Drive client secret. No route-level auth dependency was visible in the inspected definition. This is a code-level exposure concern; network reachability was not tested.
4. `build_release.py` says it preserves prior installers, but copies to an alternate filename that excludes the build number using overwrite semantics. Rebuilding a later build of the same version/channel can replace that alternate file.
5. Desktop frames use `FrameManager`/`FrameDesigner`; LAN session composition uses a separate dictionary-based `TemplateEngine`. Their relationship is not specified in code.

No tests or hardware checks were run. README’s “25/25” badge is not current verification: 45 test modules are present in the configured test directory.

## 2. Project Overview

### Startup and runtime

`vietphotobooth/main.py::main` parses kiosk/server/update arguments, loads `ConfigManager`, starts a LAN service daemon thread unless `--no-server` is supplied, then creates `QApplication`, `MainWindow`, and enters Qt’s event loop. `server.py::create_app` creates its own config, event, camera, template, print, token, and session managers. `desktop/main_window.py::MainWindow` constructs a second manager graph for the native UI. Both graphs use local configuration/storage paths, but their in-memory state is separate.

The main application is native Qt; it also serves HTML/static content and LAN API routes for phone sharing and related workflows. It is not only a native desktop surface.

### Package and configuration

Important packages are `core`, `desktop`, `camera`, `audio`, `filters`, `frames`, `processing`, `printing`, `sharing`, `cloud`, and `updates`. `ConfigManager` in `core/config.py` stores JSON by default at `%LOCALAPPDATA%\1998TeamPhotobooth\config.json`, merges it with defaults, supports dotted keys, and writes through a temporary file and replace/rename. `EventManager` defaults to `%LOCALAPPDATA%\1998TeamPhotobooth\Events`.

No `requirements.txt`, `pyproject.toml`, setup manifest, Pipfile, or lockfile was found. `README.md` lists a manual `pip install` command for PySide6, OpenCV, Pillow, NumPy, pywin32, qrcode, FastAPI, uvicorn, pytest, and PyInstaller. `vietphotobooth.spec` lists packaged data and hidden imports.

### Version and packaging

`vietphotobooth/version.py` is the declared source of version metadata: 2.0.0 / Build 206 / RC. `vietphotobooth.spec` packages `Assets`, LAN UI templates/static content, and Nikon SDK binaries. `VietPhotoBooth.iss` supplies Inno Setup defaults 1.6.6/166 and uses absolute developer paths for output and icon; `build_release.py` passes version/build defines when invoking ISCC. These are declarations, not proof that a package was built or installed.

## 3. System Architecture

The desktop window owns managers and passes them to pages. Qt signals/slots and timers connect UI actions; camera stream, face detection, printer queue, cloud sync, and some composition use threads/workers. The codebase combines Qt objects, Python threads, PIL images, NumPy arrays, and OpenCV.

`core/logger.py::get_logger` configures `VietPhotoBooth` with console INFO and rotating UTF-8 file DEBUG logging in local app data (10 MB, five backups). This was inspected statically; application handlers were not exercised.

| Subsystem | Main modules | Responsibility |
|---|---|---|
| Entry/UI | `main.py`, `desktop/main_window.py`, `desktop/widgets/*` | Desktop startup, navigation, operator/kiosk flows |
| Core | `core/config.py`, `events.py`, `state_machine.py`, `auth.py`, `logger.py` | Settings, event storage, session state, PIN, logs |
| Cameras | `camera/connection_manager.py`, `camera/backends/*` | Backend selection, frames, capture, status |
| Face/AF | `camera/face_detector.py`, `face_eye_af_controller.py` | Software landmarks and separate camera AF requests |
| Frames | `frames/frame_models.py`, `frame_manager.py`, `frame_designer.py` | JSON templates, storage and PIL rendering |
| Image | `processing/image_processor.py`, `filters/*` | Crop/resize, filters, LUT, beauty |
| Printing | `printing/manager.py`, `spooler.py`, `presets.py` | Queue, Windows spooler and printer profiles |
| QR/LAN | `sharing/token_manager.py`, `server.py` | Tokens, QR, local HTTP routes |
| Build | `vietphotobooth.spec`, `VietPhotoBooth.iss`, `build_release.py` | PyInstaller and Inno Setup |

## 4. Camera and Nikon MAID3

`camera/backends/base.py::CameraBackendBase` defines discovery, connect/disconnect, status/error, Live View, capture, capabilities, parameters, autofocus, and health checks. `camera/manager.py::CameraManager` wraps/subclasses `CameraConnectionManager`, preserving the older API.

Implemented backend classes include:

- `camera/backends/simulator.py::SimulatorBackend`: generated software images and frames.
- `camera/backends/directshow_webcam.py::DirectShowWebcamBackend`: OpenCV/DirectShow webcam discovery and capture.
- `camera/backends/digicam_control.py::DigiCamControlBackend`: localhost HTTP service (default port 5513) and configured CLI fallback.
- `camera/backends/nikon_maid/nikon_d780_backend.py::NikonD780Backend`: Nikon MAID session, capture, Live View and AF.

`CameraConnectionManager` centralizes backend switching, connection state, stream thread, frame/error callbacks, FPS tracking, and capture facade. It attempts reconnect on capture when disconnected; digiCamControl checks its process/port/camera name and uses bounded network timeouts. Static presence does not establish hardware reliability.

`NikonSDKLoader` requires 64-bit Windows and checks for `Type0026.md3`, `NkdPTP.dll`, `NkRoyalmile.dll`, and `dnssd.dll`. It prefers the package’s `bin/x64` files; a machine-specific SDK path is also a fallback. No driver change is proposed or tested.

`NikonSession::capture_photo` pauses Live View, selects SDRAM, issues MAID `CAP_START(CAPTURE)`, pumps async events, waits for `ADD_CHILD`, opens the image object, registers a data callback, issues `CAP_START(ACQUIRE)`, accumulates chunks, and restores Live View. The timeout defaults to 12 seconds. `NikonD780Backend` maps failures to camera error records.

**Unverified:** physical D780 detection, driver/SDK compatibility, AF accuracy, MUP exposure timing, reconnect, long-run behavior, and supported models beyond the explicit backend/integrations.

## 5. Live View and Capture Pipeline

`CameraConnectionManager::_stream_loop` reads frames on a background Python thread; it decodes JPEG to RGB when needed, assigns sequence IDs, keeps a latest-frame buffer, calls registered callbacks, and downsizes frames above 1280×720. It paces at a 26 ms target for Nikon MAID and 33 ms for other backends. These are target intervals, not measured frame rates.

Desktop flow: countdown timer → `KioskPage._trigger_shot` → optional AF callback/watchdog → `_execute_photo_capture` → `CameraManager.capture_photo` → backend capture → save/verify → optional Smart Beauty → review/composite. Kiosk capture calls `capture_photo` synchronously in this path. `CameraConnectionManager.capture` holds its lock while calling the backend. Nikon MAID and digiCamControl contain waits/transfers, so GUI blocking is a **verified source-level risk**, not a measured runtime failure.

Kiosk verifies the image file and decodability. On invalid output/disconnect it aborts the flow, stops countdown/audio, clears active transaction state, and requests AF cancellation. Backend timeouts and errors exist, but recovery success was not executed.

## 6. AI Beauty and Image Processing

`camera/face_detector.py::FaceEyeDetector` uses OpenCV `FaceDetectorYN` and YuNet ONNX. `FaceDetectionService` runs in a background Python thread, uses a single latest-frame buffer and a default 12 FPS target, and notifies callbacks. `FaceEyeAFController` uses detection results to request camera autofocus; software face/eye overlays and physical AF are separate mechanisms.

`processing/image_processor.py` also maintains its own cached YuNet detector for face-centered crop, resizing its input’s longest dimension to 320. This is a second detector initialization path.

`filters/beauty_engine.py::SmartBeautyEngine` uses face landmarks to create masks, then applies OpenCV bilateral smoothing/texture recovery, LAB brightening, and lip tint. This is classical image processing guided by face detection, not evidence of a learned beauty-generation model. No explicit GPU path was found in the inspected processing code; these paths use OpenCV/NumPy/PIL.

`FilterEngine` supports JSON presets, adjustments, skin smoothing, and 3D LUT via `CubeLUTParser`. `ImageProcessor` handles EXIF rotation, crop modes, face-centered crop, zoom/pan, simple filters, resize, and thumbnails. Processing quality, RAW handling, full-resolution latency, and offline runtime were not measured.

## 7. Frame Editor and Layout

`frames/frame_models.py` defines JSON-serializable `PhotoSlot`, `TextLayer`, `LogoLayer`, and `FrameTemplate`. `FrameManager` loads built-in/user frames, creates thumbnails, and supports save/import/duplicate/rename/delete and ZIP backup/restore. `FrameDesignerPage` contains an interactive canvas; `frame_tab_container.py` and `frame_gallery_page.py` provide gallery/navigation UI.

`FrameDesigner.render_composite` uses PIL to compose slot crops, rotation/flips, rounded corners/borders, duplicate slots for dual strips, transparent PNG overlay, text/logo layers, cut lines, and 300 DPI metadata. It also provides previews and validates slot bounds/bleed/safe zones. These are implemented code paths; output accuracy across all templates/printers is not hardware verified.

The LAN path uses `processing/template_engine.py::TemplateEngine`, a dictionary-based template model; desktop uses `FrameManager`/`FrameDesigner`. This separate schema/rendering architecture is verified. Whether the formats are intentionally separate or should share data is unverified and should be made explicit in future specifications.

## 8. Printing Pipeline

`PrintManager` maintains print jobs and a background queue thread. It supports printer selection, strip/full printer preferences, offsets, zoom/orientation, paper counters, warning threshold, safety margin (default 0.98), auto orientation, thermal pacing, cancel and retry. `WindowsPrintSpooler` enumerates Windows printers, reads status and submits through pywin32 device contexts. Presets and `DNPRX1HSProfile` provide paper/printer-specific data and DNP guidance.

After spool submission the manager marks `SPOOLED`, waits one second, and marks `COMPLETED`. That state is based on application/spooler flow, not confirmation that a physical printer finished. DNP RX1HS media, cut behavior, calibration, and reliability were not tested. A server test-print route can submit a real print and was not called.

## 9. QR Sharing and Storage

`EventManager` creates `Events/<event>/Originals`, `Final`, `Thumbnails`, `Templates`, and `Logs`; it lists/creates/renames/deletes events, exports ZIP, and checks disk space. Legacy migration copies missing files from the older `VietPhotoBooth\Events` tree; no automatic retention cleanup routine was found in the inspected module.

`TokenManager` generates `secrets.token_urlsafe(16)` tokens, associates them with files/events, supports expiration/revocation, and creates QR/LAN URLs. Tokens are held in memory, so active-token persistence across process restart is not implemented in this manager. Default configured expiry is 24 hours.

The server starts on `0.0.0.0` by default unless disabled; QR links use HTTP. Routes include sharing, camera, session, printer, event, config, and diagnostics. `/api/config` returns `config.all`; Settings also has a Google Drive client secret. The inspected route has no visible auth dependency; `/api/admin/verify-pin` separately returns the PIN result. This is a verified code-level exposure concern, not an exploit test. TLS, middleware, firewall, and LAN threat controls were not tested.

Google Drive sync is optional and network dependent. Local capture/storage/print code paths do not visibly require cloud access; offline behavior was not exercised.

## 10. UI/UX and Kiosk Mode

`MainWindow` creates six primary tabs (Capture, Frames, Camera, Printer, Events/Library, Settings), plus Guest Idle, Dashboard, Devices, and QR pages in a stack. PIN protection is used for camera, printer, events, and settings; frame design remains accessible. `desktop/styles.py` defines the Qt theme. Kiosk provides touch-oriented controls, countdown, shot count, frame selection, review, retake, Smart Beauty, save/print/share, fullscreen, and idle flow. `guest_review_dialog.py` implements frame/photo assignment, crop/rotate/flip, text/sticker edits, undo/history, and rendering.

The supplied `actual_ui_screenshot.png` shows the capture screen with the camera disconnected and a demo label. It is user-supplied evidence, not captured during this audit. One 1280×720 image cannot establish DPI/scaling or touchscreen behavior. Responsiveness benefits from workers/timers, but capture’s synchronous path remains an exception.

## 11. Audio and Countdown

`audio/sound_controller.py::SoundController` uses cached Qt Multimedia `QSoundEffect` objects. It tracks Loading/Ready/Error states, volume, playback history, countdown transaction marks, and shutter transaction IDs; it stops/deletes effects on cleanup. `audio/constants.py` resolves source/bundle asset paths. `vietphotobooth.spec` includes `Assets` and Qt Multimedia imports.

Audio assets found: `Assets/Audio/countdown_tick.wav`, `countdown_voice_vi.wav`, and `shutter_click.wav`. Dynamic `voice_N.wav`/`countdown_voice_N.wav` lookup is supported by code, but no per-number files were found in the audio asset directory. Playback code and package declarations do not prove audible output.

Settings use `audio.enabled`, `audio.volume`, `audio.tick_enabled`, `audio.voice_enabled`, and `audio.shutter_enabled`. `SettingsPage` emits `audio_settings_changed`; `MainWindow` connects it to a handler that calls `SoundController.sync_with_config` on the active Kiosk controller.

Kiosk starts a countdown transaction with the displayed number; each tick requests the next number. `SoundController.play_countdown_step` tracks per-number playback to avoid duplicate requests, picks a matching dynamic voice if present, otherwise falls back to tick, and stops overlapping countdown effects. `cancel_countdown` and disconnect-abort paths stop timer/audio and clear active IDs.

Shutter callback is passed from Kiosk through `CameraConnectionManager` into backends. `play_shutter_for_transaction` deduplicates transaction IDs; Kiosk checks that the transaction remains active. Simulator calls back before generating a still; DirectShow before reading its selected frame; digiCamControl after HTTP 200. Those events do not have identical physical meaning. For Nikon, callback is after `CAP_START(CAPTURE)` returns `SUCCESS`, `WAITING_2ND_RELEASE`, or zero and before waiting for `ADD_CHILD`/image transfer. It is command acceptance, not verified exposure time. In MUP, callback may precede the second release call.

Audio tests present: `test_v166_studio_audio.py` and untracked `test_dynamic_countdown_voice_sync.py`, `test_simulator_countdown_audio_timeline.py`. They were inspected, not run. No physical output device was tested.

## 12. Tests and Quality Assurance

`pytest.ini` sets `testpaths = vietphotobooth/tests` and `addopts = --capture=sys`. The configured test directory contains 45 Python modules; static search found 357 declarations matching `def test_` or `class Test` (inventory only, not an executed test count). Coverage areas include config/events, GUI, camera/Nikon, AF/face, frames, filters/LUT, printing, QR/server, cloud, updates/release, audio, and v2.0.

`vietphotobooth/tests/conftest.py` forces Qt offscreen mode, cleans widgets, and calls `os._exit` at `pytest_unconfigure` with the recorded exit code to avoid Qt/Windows teardown crashes. This process-exit behavior matters when interpreting finalizers and test cleanup.

README advertises 25/25 tests; that statement is not a current test result. No tests, CI reports, app launch, device, print, or performance test were run for this audit.

## 13. Known Issues and Risks

| Priority | Finding | Evidence/status |
|---|---|---|
| High | LAN all-interface listener plus full config response containing settings that may hold secrets; no auth dependency visible at that route. | `main.py`, `server.py` `/api/config`, `settings_page.py`. **Code-level risk verified; network exposure untested.** |
| High | Desktop capture is synchronous through the Kiosk call path while backend capture waits/transfers. | `kiosk_page.py::_execute_photo_capture`, `connection_manager.py::capture`, `maid_session.py::capture_photo`. **Source risk verified; freeze unmeasured.** |
| High | Nikon callback indicates MAID command result, not physical shutter; MUP callback precedes second release. | `maid_session.py::capture_photo`. **Ordering verified; physical timing unverified.** |
| Medium | digiCamControl HTTP callback follows HTTP 200; CLI fallback equivalence needs review. | `digicam_control.py::capture_photo`. **Partially verified; fallback not executed.** |
| Medium | Desktop and LAN use different template models/renderers. | `frame_models.py`, `frame_designer.py`, `template_engine.py`, `server.py`. **Duplication verified; intended contract unknown.** |
| Medium | Release script copies to an alternate filename without build number using `shutil.copy2`, which can overwrite. | `build_release.py` alternate installer section. **Source verified; build not run.** |
| Medium | Installer defaults contain old 1.6.6/166 macros and machine-specific absolute paths. | `VietPhotoBooth.iss`. **Verified.** |
| Medium | README’s test badge does not match the present suite inventory and has no current run evidence. | `README.md`, `pytest.ini`, test directory. **Verified mismatch.** |
| Medium | `cleanup_transactions` exists but no caller was found in the package search; transaction maps may grow for the controller lifetime. | `sound_controller.py`, Kiosk cleanup. **Partially verified; impact unmeasured.** |
| Low | Two YuNet initialization paths exist for Live View/beauty and face-centered crop. | `face_detector.py`, `image_processor.py`. **Verified.** |

## 14. Technical Debt

- Desktop and LAN manager graphs have separate in-memory state.
- Two template schemas/rendering paths can drift.
- GUI capture is synchronous while camera I/O can block.
- Capture-start callbacks have backend-specific semantics grouped behind one callback name.
- Two YuNet initialization paths can diverge in sizing/threshold/runtime configuration.
- Optional cloud and updater use external network/auth, so offline degradation needs explicit acceptance tests.
- Installer script is tied to a developer path and its alternate output may collide across builds.
- The current uncommitted tree is not a reproducible clean baseline; future specs should record commit hash and dirty status.

## 15. Missing or Unverified Areas

Not established by this static audit: actual Nikon detection, Live View continuity, physical shutter timing, AF quality, transfer/reconnect; supported camera/firmware matrix; audible playback or packaged QSoundEffect readiness; physical DNP printer output/cutting; real LAN authorization/TLS/firewall; measured FPS, latency, GUI responsiveness, beauty quality or long-run memory; event retention policy; frame renderer equivalence; Windows DPI/touchscreen coverage; and Build 206 test pass rate.

## 16. Module and Dependency Map

| Path | Main symbols | Role |
|---|---|---|
| `vietphotobooth/main.py` | `main`, `run_sharing_server` | Qt entry and LAN server thread |
| `desktop/main_window.py` | `MainWindow` | Manager/page composition, navigation and settings wiring |
| `core/config.py` | `ConfigManager` | JSON config and PIN hash operations |
| `core/events.py` | `EventManager` | Event storage and operations |
| `core/state_machine.py` | `SessionManager` | LAN capture session sequence |
| `camera/connection_manager.py` | `CameraConnectionManager` | Backend/stream/capture coordination |
| `camera/backends/*` | backend classes | Simulator, webcam, digiCamControl and Nikon |
| `camera/backends/nikon_maid/*` | `NikonSession`, `NikonCameraWorker`, `NikonD780Backend` | MAID/DLL access and D780 operations |
| `camera/face_detector.py` | `FaceEyeDetector`, `FaceDetectionService` | YuNet face/eye detection |
| `camera/face_eye_af_controller.py` | `FaceEyeAFController` | AF decision/trigger coordination |
| `audio/sound_controller.py` | `SoundController` | QSoundEffect lifecycle and transaction state |
| `filters/beauty_engine.py` | `SmartBeautyEngine` | Landmark-guided smoothing/brightening/tint |
| `filters/filter_engine.py`, `lut_parser.py` | `FilterEngine`, `CubeLUTParser` | Presets, parametric filters, 3D LUT |
| `frames/frame_models.py` | `FrameTemplate`, slots/layers | JSON frame schema |
| `frames/frame_manager.py` | `FrameManager` | Frame persistence/import/listing |
| `frames/frame_designer.py` | `FrameDesigner` | PIL composition and validation |
| `processing/template_engine.py` | `TemplateEngine` | LAN dictionary-template renderer |
| `printing/manager.py`, `spooler.py` | `PrintManager`, `WindowsPrintSpooler` | Queue and Windows print API |
| `sharing/token_manager.py`, `server.py` | `TokenManager`, `create_app` | QR tokens and HTTP routes |
| `cloud/sync_manager.py` | `SyncManager`, `SyncWorker` | Optional Drive queue |
| `vietphotobooth.spec`, `VietPhotoBooth.iss`, `build_release.py` | packaging | PyInstaller/Inno Setup |

## 17. Recommendations for Future Specifications

1. Define separate capture events for request, backend acceptance, physical exposure where provable, data arrival, transfer complete, save, failure, and cancellation. State each backend’s evidence level.
2. Specify that camera capture/transfer and rendering cannot block Qt UI; define measurable latency and timeout acceptance by backend.
3. Decide whether desktop and LAN workflows share state; define the state owner and synchronization contract.
4. Choose a canonical template schema or define conversion/version compatibility between the two models.
5. Specify LAN threat model, bind address, route authorization, secret redaction, guest permissions, token expiry/revocation, and transport security.
6. Define originals/final/thumbnail/log retention, backup, recovery, and deletion authorization.
7. Define camera hardware/driver/firmware acceptance matrix without replacing working Windows drivers absent evidence and approval.
8. Define spool-submission versus physical completion, DNP media/cut/calibration, retry and duplicate-print behavior.
9. Specify beauty color spaces, supported inputs, CPU/GPU path, quality/performance thresholds, and fallback; distinguish classical CV from learned models.
10. Specify audio readiness/error, physical-output test, MUP timing, cancellation, deduplication and backend callback semantics.
11. Tie test badges/reports to a commit/build; require current full-suite and relevant hardware evidence.
12. Define reproducible dependency manifests and packaging paths; prevent installer collisions.

## 18. Scope, Limitations, and Evidence Index

### Scope

- Read project instructions (`AGENTS.md`, `GEMINI.md`, `.specify/memory/constitution.md`), README, package source, tests, config, and build scripts.
- Recorded initial Git status before inspection.
- No existing source, test, config, or document was modified. No tests, installs, builds, app sessions, or hardware tests were run.
- The report describes the current working tree including uncommitted changes and is not a clean-commit baseline.

### Evidence labels

- **VERIFIED:** Directly located in current source/config/test declarations.
- **PARTIALLY VERIFIED:** Implementation exists, but relevant paths/runtime are not fully established.
- **UNVERIFIED:** Requires runtime, hardware, deployment, or security testing.
- **NOT IMPLEMENTED/NOT FOUND:** No implementation located in inspected paths; not a claim about unsearched code.

### Evidence index

- Governance/startup/config: `AGENTS.md`, `GEMINI.md`, `.specify/memory/constitution.md`, `vietphotobooth/main.py`, `desktop/main_window.py`, `core/config.py`, `core/logger.py`.
- Camera/MAID: `camera/manager.py`, `camera/connection_manager.py`, `camera/backends/base.py`, `camera/backends/device_discovery.py`, `camera/backends/simulator.py`, `directshow_webcam.py`, `digicam_control.py`, `camera/backends/nikon_maid/{maid_loader.py,maid_session.py,camera_worker.py,nikon_d780_backend.py}`.
- AI/processing: `camera/face_detector.py`, `camera/face_eye_af_controller.py`, `processing/image_processor.py`, `processing/template_engine.py`, `filters/beauty_engine.py`, `filters/filter_engine.py`, `filters/lut_parser.py`.
- Frames/UI: `frames/frame_models.py`, `frame_manager.py`, `frame_designer.py`, `desktop/widgets/{kiosk_page.py,live_viewport.py,frame_gallery_page.py,frame_tab_container.py,frame_designer_page.py,guest_review_dialog.py}`.
- Print/storage/sharing: `printing/{manager.py,spooler.py,presets.py,dnp_rx1hs.py}`, `core/{events.py,state_machine.py}`, `sharing/token_manager.py`, `server.py`, `cloud/sync_manager.py`.
- Audio/tests/build: `audio/{constants.py,sound_controller.py}`, `desktop/widgets/settings_page.py`, `pytest.ini`, `vietphotobooth/tests/*`, `vietphotobooth.spec`, `VietPhotoBooth.iss`, `build_release.py`, `vietphotobooth/version.py`.
- Supplied references: `actual_ui_screenshot.png`, `test_nikon_live_frame.jpg`; neither was captured or measured during this audit.

### Initial Git status recorded

Branch: `feature/v2.0.0-photobooth`.

Modified tracked paths (18):

- `vietphotobooth/audio/constants.py`
- `vietphotobooth/audio/sound_controller.py`
- `vietphotobooth/camera/backends/digicam_control.py`
- `vietphotobooth/camera/backends/directshow_webcam.py`
- `vietphotobooth/camera/connection_manager.py`
- `vietphotobooth/desktop/styles.py`
- `vietphotobooth/desktop/widgets/dashboard_page.py`
- `vietphotobooth/desktop/widgets/devices_page.py`
- `vietphotobooth/desktop/widgets/events_page.py`
- `vietphotobooth/desktop/widgets/kiosk_page.py`
- `vietphotobooth/desktop/widgets/live_viewport.py`
- `vietphotobooth/desktop/widgets/printing_page.py`
- `vietphotobooth/desktop/widgets/qr_sharing_page.py`
- `vietphotobooth/desktop/widgets/session_lightbox_dialog.py`
- `vietphotobooth/desktop/widgets/settings_page.py`
- `vietphotobooth/desktop/widgets/smart_beauty_panel.py`
- `vietphotobooth/desktop/widgets/touch_pin_dialog.py`
- `vietphotobooth/tests/test_v200_rc2_hardening.py`

Untracked entries recorded at start: nine `.agents/skills/speckit-*/` directories, `.specify/`, and two test files:

- `vietphotobooth/tests/test_dynamic_countdown_voice_sync.py`
- `vietphotobooth/tests/test_simulator_countdown_audio_timeline.py`

These were pre-existing user-owned changes and were not staged, edited, or removed.
