# Baseline Audit Validation — 1998 TEAM Photobooth

**Validation date:** 2026-11-04 (Asia/Saigon)  
**Repository:** C:\Users\Admin\Documents\photobooth  
**Branch / HEAD at inspection:** feature/v2.0.0-photobooth / 08bfb13c54c142da3342114425ce195634cd04f3  
**Baseline reviewed:** docs/BASELINE_SYSTEM_AUDIT.md  
**Method:** Read-only static source and test inspection of the current working tree. No tests, application, network probes, camera, printer, or build were run. Findings describe source behavior, not deployed behavior.

## Scope and repository state

The baseline audit exists (28,828 bytes) and was not edited. At the start of this validation, the working tree already contained 18 modified tracked files and untracked Spec Kit/agent-skill materials, two tests, and the baseline audit itself. Those pre-existing changes were preserved. The validation document was absent at the start. No source, test, configuration, Constitution, or Git metadata was changed; this report is the only path added during this validation.

## Summary verdicts

| Finding | Verdict | Severity | Confidence |
|---|---|---:|---:|
| LAN security and /api/config | Confirmed; PIN hash is filtered but other secrets are not | High | High for source behavior; deployment exposure unverified |
| Desktop Kiosk capture blocking | Confirmed source-level GUI-thread blocking path | High | High for call path; runtime freeze duration unmeasured |
| Nikon shutter timing | Callback ordering confirmed; not proof of physical shutter/exposure | High | High for code ordering; low for physical timing |
| Desktop/LAN frame compatibility | Separate schemas/renderers confirmed; no adapter found | Medium | High for inspected repository |
| Release output safety | Collision/overwrite paths confirmed; preservation claim contradicted | High | High for script paths; no build executed |
| Countdown audio guarantees | Request/dedup logic exists; correct audible playback is not guaranteed | Medium | High for source behavior; actual playback unverified |

## 1. LAN security and configuration exposure

**Verdict — Confirmed, with one correction to the baseline wording.** FastAPI app creation in vietphotobooth/server.py, create_app has no middleware registration or route authentication dependency. Route definitions do not use Depends for authorization. POST /api/admin/verify-pin checks the supplied PIN and returns a boolean; it does not establish a session, issue an authorization token, or gate other endpoints. vietphotobooth/main.py, main starts the service on 0.0.0.0 unless --no-server is supplied.

GET /api/config returns config.all. ConfigManager.all makes a shallow copy and removes only admin_pin_hash; it does not redact cloud.gdrive_client_secret or other values. SettingsPage reads and writes cloud.gdrive_client_secret. Therefore, the PIN hash itself is not exposed by config.all, but the client secret and any other configured sensitive values remain exposed in the response. POST /api/config accepts a dictionary and calls config.update(data) without an auth check in the route.

**Static attack surface identified (not probed):**

- Public pages/assets: /, /admin, /s/{token}, /static/*.
- Session control: GET /api/session/status; POST /api/session/start, /cancel, /reset, /print.
- Camera access/control: /api/camera/liveview, /info, /devices, /switch, /compatibility (GET except /switch, POST).
- Printer inspection/control: /api/printer/list, /queue, /dnp-guide (GET); /select, /cancel, /retry, /test (POST). /test can cause a real print; it was not called.
- Template and event control: /api/templates (GET), /api/templates/select (POST), /api/events (GET), /api/events/create, /switch, /rename (POST), /api/events/export/{event_name} (GET).
- Gallery/photo access: /api/gallery, /api/photo/{category}/{filename} (GET).
- Sharing controls/downloads: /api/sharing/tokens (GET), /api/sharing/revoke (POST), /api/sharing/qr/{token}, /download/{token}, /download/{token}/all (GET).
- Admin/config/diagnostics: /api/admin/verify-pin (POST), /api/config (GET/POST), /api/diagnostics and /api/logs (GET).

This inventory comes from route declarations, not a penetration test. Tokenized download routes require a token to locate content, but that bearer-token design does not authorize other routes. Default FastAPI docs/OpenAPI routes may also exist because FastAPI() is created without disabling them; reachability was not tested. Listener reachability depends on Windows firewall, network topology, and runtime arguments, none of which were tested.

**Tests inspected:** vietphotobooth/tests/test_session_and_server.py, test_fastapi_endpoints calls several routes without credentials and checks the PIN endpoint, but does not request /api/config, assert redaction, require authorization on privileged routes, or validate bind/TLS behavior. test_v200_rc2_hardening.py includes server-related hardening coverage, but no located test establishes route-wide authorization or secret filtering.

**Severity / confidence:** High severity; high confidence that source exposes the unredacted config response and leaves handlers without route auth. Remote LAN reachability is deployment dependent.

**Future specification topics:** LAN trust boundary and intended clients; default bind address; route-by-route roles; PIN-to-session/token flow; field allowlist and secret redaction; token scope/expiry/revocation; logging privacy; TLS/firewall assumptions; tests proving unauthorized requests fail.

## 2. Kiosk → CameraManager → backend capture and Qt blocking

**Verdict — Confirmed source-level blocking risk.** Desktop route: KioskPage.start_capture_flow → QTimer.timeout connected to _on_countdown_tick → _trigger_shot → optional AF completion/watchdog callback → _execute_photo_capture → CameraManager.capture_photo → inherited CameraConnectionManager.capture_photo/capture → selected backend capture_photo. CameraManager subclasses CameraConnectionManager and does not dispatch this operation to a worker. The countdown timer belongs to KioskPage; its slot and direct calls execute on the GUI thread. The optional AF callback is marshalled with QTimer.singleShot(0, self, _apply), but _apply then calls capture directly on the UI thread.

CameraConnectionManager.capture holds its manager lock while invoking backend.capture_photo. NikonD780Backend calls NikonCameraWorker.capture, which calls NikonSession.capture_photo synchronously; that stops Live View, sleeps, pumps MAID calls, polls for ADD_CHILD, and transfers image chunks. The backend passes a 12-second timeout, but the implementation has multiple wait/transfer phases; this value should not be treated as a measured total upper bound. digiCamControl performs HTTP calls, polling up to eight seconds, image download, and potentially subprocess.run with an eight-second timeout. DirectShow reads a frame synchronously. Simulator is also called synchronously.

_execute_photo_capture then synchronously saves through the manager, checks file size, verifies the saved image with PIL, may copy the original, and continues into beauty/review flow. Widget updates, input, repaint, and other timer callbacks can be delayed while this stack runs. Live-view streaming and Nikon frame work run on background threads; face detection/controller and print queue also use workers, but these do not move this still-capture call off the GUI thread. Lock contention can affect other callers needing the manager lock.

**Tests inspected:** test_camera_connection_manager.py covers manager/capture behavior; test_nikon_maid_backend.py and test_v154_autofocus_and_face_detection.py cover backend contracts and AF mocks; test_kiosk_face_eye_af_capture.py covers capture/AF orchestration. No located test records GUI thread identity during still capture, asserts event-loop responsiveness while a backend blocks, or measures freezes across backends.

**Severity / confidence:** High severity for kiosk responsiveness; high confidence in the direct call/thread relationship. Actual stall duration and visible impact require runtime testing.

**Future specification topics:** Capture worker ownership; immutable transaction/result messages; Qt-thread-only UI updates; lock boundaries; cancellation/timeouts; UI responsiveness limits; deterministic slow-backend tests; camera timeout recovery.

## 3. Nikon MAID capture and shutter callback timing

**Verdict — Ordering is confirmed; callback meaning must remain evidence-based.** NikonD780Backend.capture_photo delegates to NikonCameraWorker.capture, which calls NikonSession.capture_photo. In the MAID session:

1. Live View may stop and the save target is set to SDRAM.
2. First _entry(CAP_START, CAPTURE) is issued and its immediate result is stored in ret.
3. If on_capture_start exists and ret is SUCCESS, WAITING_2ND_RELEASE, or 0, the callback runs immediately.
4. The code sleeps 0.3 seconds and pumps async events.
5. If completion result cap_res[0] or ret is WAITING_2ND_RELEASE, a second CAP_START(CAPTURE) is issued.
6. It waits for ADD_CHILD indicating a new camera item, opens the item/data object, starts CAP_START(ACQUIRE), collects callback chunks, and returns the reconstructed JPEG after acquisition/validation.

In WAITING_2ND_RELEASE, shutter sound callback can run before the second release call. For other accepted return codes, it still indicates MAID command result/acceptance, not hardware-confirmed shutter release or exposure timestamp. ADD_CHILD indicates an item became available; ACQUIRE/chunk completion indicates transfer progress. No physical shutter sensor or exposure-start timestamp appears in this source path. Distinguish command acceptance, second-release request, item/data availability, transfer completion, and file validation.

**Tests inspected:** Nikon tests cover loader/backend contract and mocked lifecycle; test_v154_autofocus_and_face_detection.py covers AF and worker capture-with-AF. No located test asserts the MAID sequence for first/second release, callback ordering under WAITING_2ND_RELEASE, or timing against physical exposure. Tests cannot prove D780 physical shutter synchronization.

**Severity / confidence:** High for callback ordering risk; high confidence in source order. Physical timing confidence is low without Nikon/MAID runtime and hardware observation.

**Future specification topics:** Backend-neutral capture events; evidence level per backend; MUP/two-step state machine; callback semantics; physical timing method; audio latency calibration; separation of capture acceptance, exposure, and transfer completion.

## 4. Desktop FrameTemplate versus LAN TemplateEngine

**Verdict — Separate models/renderers confirmed; no conversion/synchronization path located.** Desktop frames use vietphotobooth/frames/frame_models.py, FrameTemplate and nested PhotoSlot, TextLayer, LogoLayer. Its JSON includes id/name/category/type/canvas_size/background fields, overlay path, slots with rotation/borders/fit/crop fields, text_layers, logo_layers, bleed/safe-zone and print metadata. FrameManager persists these objects; FrameDesigner renders the desktop schema.

LAN composition uses vietphotobooth/processing/template_engine.py, DEFAULT_TEMPLATES and TemplateEngine. Its dictionaries contain fields such as id/name/type/canvas_size/bg_color/text_color, simple x/y/w/h slots, text_area, and optional dual-strip fields. server.py creates this engine under configured storage Templates; SessionManager consumes it. Repository search found no adapter, migration, shared serializer, or route importing desktop FrameTemplate objects into TemplateEngine. Shared JSON extension or overlapping field names do not establish compatibility.

**Tests inspected:** test_frames_and_designer.py covers desktop models/designer; test_processing_and_templates.py covers LAN template rendering; test_session_and_server.py covers LAN template listing/session behavior. No cross-schema round-trip, import/export compatibility, synchronization, or visual parity test was found.

**Severity / confidence:** Medium architectural risk; high confidence that checked-in code has distinct schemas and no discovered adapter. Whether this is intentional remains a product decision.

**Future specification topics:** Canonical schema or versioned adapter; coordinate units/DPI; slot identity/order/crop semantics; text/logo/overlay parity; dual-strip behavior; ownership and synchronization direction; migration and compatibility tests.

## 5. Release output and overwrite safety

**Verdict — “Never overwrites prior versions” is contradicted by output naming and writes.** build_release.py, main derives a version/build/channel primary filename under PROJECT_ROOT/dist_installer. It invokes PyInstaller with the project spec, --clean, and -y; the spec declares a one-folder output named 1998TeamPhotobooth, and the script later reads dist/1998TeamPhotobooth/1998TeamPhotobooth.exe. The -y option allows replacement of existing build outputs. The script does not check whether installer names already exist.

Primary installer: dist_installer/1998-TEAM-Setup-v{version}-Build{build}{channel}.exe. Companion {filename}.sha256 is written with Path.write_text, replacing an existing sidecar. Inno Setup receives that same base filename, while VietPhotoBooth.iss sets OutputDir to the hard-coded C:\Users\Admin\Documents\photobooth\dist_installer. Repeating the same version/build/channel targets the same primary name. The friendly copy is 1998-TEAM-Photobooth-Setup-v{version}{channel}.exe, omitting build number; shutil.copy2 replaces an existing destination, and its sidecar is also overwritten. A later build of the same version/channel can replace the friendly copy even when build number differs. No old installer is explicitly deleted, but colliding names can be overwritten.

VietPhotoBooth.iss defaults to v1.6.6/Build166 if no defines are passed, writes to the same fixed output directory, and uses OutputBaseFilename. Its [Files] entry installs the PyInstaller folder recursively into {app} with ignoreversion; this is an install-time replacement policy, not another build artifact. Source/icon paths are hard-coded. No claim is made about compiler prompting on existing targets; there is no collision guard in the script, and no build was run.

**Tests inspected:** test_v155_release_audit.py includes static/package checks and an optional test tied to an existing installer; comments mention replacement of a specific old binary. No located test proves collision-safe output, preservation of installer/hash sidecars, or same-name repeat behavior. Build/install tests were not run.

**Severity / confidence:** High for artifact integrity; high confidence in explicit output targets and same-name collisions. Exact compiler behavior for an existing output was not executed.

**Future specification topics:** Immutable artifact naming including build/channel/commit; fail-if-exists policy; atomic writes; hash consistency; isolated build/work/dist dirs; reproducibility; temp-dir collision tests; installer upgrade policy separated from artifact preservation.

## 6. Countdown state, dynamic voice lookup, fallback, deduplication, cancellation

**Verdict — Duration changes are supported between runs; audible playback and live retiming are not guaranteed.** KioskPage connects QTimer.timeout to _on_countdown_tick. _start_single_shot_countdown snapshots countdown_duration into countdown_remaining, displays it, creates a transaction ID, starts it in SoundController, requests audio for the initial value, and starts a one-second timer. Each tick decrements that snapshot and requests audio for the displayed positive value; at zero it stops the timer and triggers capture. _set_countdown_duration updates the selection. The capture flow disables countdown selector buttons during the run, so normal UI changes happen between runs. A direct/config change does not rebase active countdown_remaining.

SoundController.play_countdown_step deduplicates by transaction ID and number, but records a number only after play_sound returns true. Voice lookup is dynamic for voice_N.wav and countdown_voice_N.wav; countdown_voice_vi.wav is a fallback only for number 3. If a matching voice file is absent, it falls back to countdown_tick.wav when enabled. The baseline inventory found generic voice/tick/shutter assets, not a per-number voice file for every value. play_sound rejects effects in Error status, but does not require Ready; it may call QSoundEffect.play() while loading and append to playback history. A successful return/history entry means playback was requested, not confirmed audible output. The 1,000 ms timer cadence is not synchronized to each sound asset's duration.

Kiosk cancellation stops the timer and audio. SoundController.cancel_countdown_transaction clears the active ID only if it matches, but calls stop_countdown_audio regardless; stale cancellation could stop sound for a newer transaction. Kiosk normally passes its current ID. Shutter dedup records the transaction before checking whether audio is enabled or playback succeeds, so retrying with the same ID will not retry the sound; this is an exactly-once request policy, not an audible guarantee.

**Tests inspected:** test_v166_studio_audio.py, test_dynamic_countdown_voice_sync.py, test_simulator_countdown_audio_timeline.py cover settings, expected number sequences, changing durations between runs, fallback selection, deduplication, cancellation, and simulator timeline state. Not run. Missing coverage includes in-flight duration mutation semantics, stale cancellation against a newer transaction, QSoundEffect Loading behavior, actual device output/readiness, dropped/delayed audio, measured camera event alignment, and physical Nikon timing.

**Severity / confidence:** Medium for audible cue/timing correctness; high confidence in source state/selection behavior and its limitations. Actual output, device readiness, sound latency and synchronization require runtime testing.

**Future specification topics:** Countdown snapshot/live-update contract; voice asset completeness/locale; readiness/error fallback; timing tolerance; cancellation race semantics; distinguish playback request from output confirmation; backend-specific shutter event meaning; simulator and hardware acceptance scenarios.

## Remaining runtime/hardware validation requirements

- **LAN:** In an authorized isolated environment, verify bind/firewall reachability, HTTP behavior, and intended authorization policy after a future fix. No network probe was performed.
- **Desktop capture:** Use deliberately slow/failing backends to measure event-loop responsiveness and thread affinity; Nikon and digiCamControl runs are needed for real latency.
- **Nikon:** D780/MAID hardware tests are required for MUP, physical shutter/exposure timing, and audio synchronization.
- **Frames:** Round-trip/import and visual parity tests are needed if desktop/LAN interchange is required.
- **Release:** Test collision policy in a disposable output directory; no build was run.
- **Audio:** Verify QSoundEffect readiness and audible output on supported Windows devices; test cancellation/reconfiguration and simulator/hardware timing separately.

## Verification record

- Source paths reviewed: vietphotobooth/server.py, main.py, core/config.py, desktop/widgets/settings_page.py, desktop/widgets/kiosk_page.py, camera/manager.py, camera/connection_manager.py, camera/backends/*, camera/backends/nikon_maid/{camera_worker.py,maid_session.py,nikon_d780_backend.py}, frames/{frame_models.py,frame_manager.py,frame_designer.py}, processing/template_engine.py, audio/{constants.py,sound_controller.py}, build_release.py, VietPhotoBooth.iss, vietphotobooth.spec.
- Tests inspected, not run: test_session_and_server.py, test_v200_rc2_hardening.py, test_camera_connection_manager.py, test_kiosk_face_eye_af_capture.py, Nikon MAID/AF tests, frame/template tests, test_v155_release_audit.py, test_v166_studio_audio.py, test_dynamic_countdown_voice_sync.py, test_simulator_countdown_audio_timeline.py.
- No tests, app, LAN service, audio output, camera, printer, installer compiler, or release build was executed.
- No source/config/test/original-audit file was modified. The only path added during this validation is docs/BASELINE_AUDIT_VALIDATION.md.


