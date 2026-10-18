# Changelog

## v0.1.0-preview.4

- Add direct, smooth, graph-centered pan and proportional zoom for legacy XPresso
  editors in both floating and docked layouts.
- Replace fixed XPresso and Timeline image addresses and whole-binary Timeline
  hash checks with guarded runtime implementation discovery. Both integrations
  now fail closed when their expected private ABI cannot be identified.
- Discover the live embedded Timeline user area and use SDK wrappers for dialog
  geometry, coordinate conversion, visibility, scrolling, and redraw.
- Record synthesized wheel and magnify input as a rejected XPresso approach: it
  maps vertical wheel input to stepped zoom, ignores horizontal pan, and cannot
  provide the requested simultaneous smooth pan and zoom.
- Classify modern Node and legacy XPresso surfaces separately and add
  discovery/routing/transport regressions for both hosting modes.
- Correct the shared navigation-axis mapping so cap lift/drop is vertical pan or
  scroll and fore/aft motion is zoom.

- Build all six native libraries for macOS 14.0 and validate architecture,
  signatures, and deployment targets during release packaging.

## v0.1.0-preview.3

- Fix floating Node Editor navigation stopping after adding or duplicating a node.
  Cinema 4D appends ` *` to the modified window title; graph discovery and input
  routing now recognize both clean and modified titles, including the inspector.
- Add regression coverage for native discovery, guarded floating-surface recognition,
  and input routing. Registered Maxon IDs and navigation tuning remain unchanged.

## v0.1.0-preview.2

- Replace temporary IDs with registered Maxon IDs: settings command 1071577,
  input service 1071578, preferences 1071579.
- Test startup and standalone Preferences registration, including the extracted package.

## v0.1.0-preview.1

- First packaged macOS ARM64 preview, installation guide, checksums, and MIT license.
- Archive earlier experiments in [Development history](DEVELOPMENT_HISTORY.md).
