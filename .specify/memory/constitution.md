
# 1998 TEAM Photobooth Constitution

## Core Principles

### I. Preserve Existing Architecture

- Existing architecture, working features, user configurations, and established workflows MUST be preserved.
- Before modifying code, agents MUST inspect the relevant implementation and understand its dependencies.
- No broad refactoring, replacement of working modules, or removal of existing functionality without explicit user approval.
- Changes MUST remain focused on the requested scope.
- Existing uncommitted changes MUST never be discarded, overwritten, reset, or silently modified.
- Backward compatibility MUST be maintained unless a breaking change is explicitly approved.

### II. Offline-First Operation

- Core photobooth workflows MUST operate without an Internet connection.
- Camera capture, local image processing, frame composition, printing, and local session management MUST NOT depend on cloud services.
- Internet-dependent features MUST degrade gracefully when connectivity is unavailable.
- Local storage MUST remain the primary source of truth for event photos and session data.
- QR sharing MUST support the project's intended local-network or offline delivery architecture.

### III. Hardware and Camera Reliability

- Camera integration MUST use clearly separated and maintainable backends.
- Existing camera backends and their working communication protocols MUST be preserved.
- Hardware-specific changes MUST NOT introduce regressions in other supported camera models.
- USB, PTP, Live View, capture, image transfer, and device disconnection MUST be handled safely.
- Printer compatibility and Windows driver stability MUST be prioritized.
- Hardware-dependent functionality MUST provide suitable simulation or mocked tests where physical hardware is unavailable.
- Existing Windows camera drivers MUST NOT be replaced without explicit approval.

### IV. Professional User Experience

- The interface MUST support event operators and touchscreen workflows.
- UI changes MUST preserve existing functional workflows unless explicitly requested otherwise.
- The 1998 TEAM visual identity, typography, icons, and design consistency MUST be maintained.
- UI operations MUST remain responsive during camera capture, image processing, and printing.
- Long-running operations MUST provide clear progress and error feedback.
- Performance optimization MUST NOT compromise image quality or functional correctness.

### V. Data Integrity and Privacy

- Original photos MUST be preserved unless deletion is explicitly requested.
- Session data, event information, generated images, and print outputs MUST be handled consistently.
- Destructive file operations MUST require explicit authorization.
- Temporary files and generated artifacts MUST have predictable lifecycle management.
- Customer photos and personal information MUST NOT be transmitted to external services without authorization.
- QR sharing MUST not expose unrelated sessions or private files.

### VI. Test-Driven Development and Quality Assurance

- Every code change MUST include appropriate validation.
- Bug fixes SHOULD include regression tests reproducing the original failure.
- New features MUST include tests for their expected behavior.
- Integration tests MUST cover important interactions between camera, UI, storage, image processing, and printing where applicable.
- The complete test suite MUST be executed using:

  `py -3.12 -m pytest`

- A release MUST NOT be declared successful if required tests fail.
- Test failures MUST be reported accurately; agents MUST NOT hide, skip, or misrepresent failures.

### VII. Mandatory Versioning and Release Management

- Every source-code modification MUST follow the mandatory release policy in AGENTS.md and GEMINI.md.
- `vietphotobooth/version.py` MUST remain the single source of truth for:
  - `__version__`
  - `__build__`
  - `__release_date__`
- Every source-code change MUST update the version, increment the build number, and update the release date.
- The full test suite MUST pass before release.
- The release build MUST use:

  `py -3.12 build_release.py`

- Installer filenames MUST follow:

  `1998-TEAM-Setup-v{__version__}-Build{__build__}.exe`

- Existing installers in `dist_installer/` MUST never be deleted or overwritten.
- Every release MUST include a `.sha256` checksum.
- Release reports MUST include version, build number, installer path, file size, and SHA-256.
- Agents MUST NOT claim a release is complete until the actual build and verification have succeeded.

## Technical Constraints

- Target platform: Windows desktop.
- The application MUST remain suitable for offline event deployment.
- Existing camera, image processing, printing, and local storage integrations MUST be preserved.
- Dependencies MUST be justified and compatible with the existing environment.
- New external services MUST NOT become mandatory dependencies for core workflows.

## Development Workflow

1. Inspect project guidance, architecture, and current Git status.
2. Understand the requested change and identify affected components.
3. Define requirements and acceptance criteria.
4. Create or update tests where appropriate.
5. Implement only the approved scope.
6. Run relevant tests and the complete test suite.
7. Update version and build metadata for source changes.
8. Build and verify the installer.
9. Generate SHA-256 checksum.
10. Report all changes, test results, and release artifacts.

If a required step cannot be completed, agents MUST stop and clearly report the limitation rather than claiming success.

## Governance

- This Constitution defines the project's engineering principles and quality standards.
- AGENTS.md and GEMINI.md provide mandatory operational instructions, especially versioning, testing, and release procedures.
- In case of conflicting instructions, agents MUST stop and request clarification rather than silently ignoring either requirement.
- Any amendment to this Constitution requires explicit project-owner approval.
- No agent may weaken data protection, release safety, or existing functionality requirements without approval.

**Version**: 1.0.0  
**Ratified**: 2026-11-04  
**Last Amended**: 2026-11-04
