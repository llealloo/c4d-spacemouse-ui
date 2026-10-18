# Changelog

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
