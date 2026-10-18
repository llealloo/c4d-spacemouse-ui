# SpaceMouse UI for Cinema 4D

SpaceMouse navigation for the rest of Cinema 4D: Node graphs, the Timeline,
lists, inspectors, and native Open/Save dialogs.

Works alongside the **unmodified 3Dconnexion Cinema 4D plugin and driver**,
which continue to handle normal 3D viewport navigation. Keep both installed
and the driver running. No vendor files or driver profiles are changed;
compatibility workarounds are applied in memory while Cinema 4D is running.

## What it adds and fixes

- Pan and graph-centered zoom in floating and docked Node Editors.
- Smooth Dope Sheet/F-Curve navigation and Timeline track-list scrolling.
- Scrolling in lists, inspectors, and macOS Open/Save dialogs.
- Independent sensitivity settings in **Preferences > SpaceMouse UI**.
- Workarounds for component-mode navigation stutter and orthographic component hover.

## Download and install

**Only tested on macOS Apple Silicon with Cinema 4D 2027.** The downloadable
build is macOS ARM64 only. Windows, Linux, Intel Macs, and other Cinema 4D
versions have not been tested. Some workarounds require exact vendor/C4D builds.

1. Download the plugin ZIP from [Releases](https://github.com/llealloo/c4d-spacemouse-ui/releases).
2. Quit Cinema 4D and extract the ZIP.
3. Copy the `SpaceMouseUI` folder into the `plugins` folder inside your Cinema 4D
   preferences folder (use **Open Preferences Folder** in Cinema 4D to locate it).
4. Restart Cinema 4D. Open **Preferences > SpaceMouse UI** or **Extensions > SpaceMouse UI**.

See [installation and compatibility notes](docs/INSTALLATION.md) for upgrades,
permissions, removal, and preview limitations. This is an experimental preview
using dedicated Maxon plugin IDs.

## Development

Build with `python3 tools/c4d-plugin/build.py` on macOS with Python 3, Xcode
Command Line Tools, and the installed 3Dconnexion framework. Output:
`.build/plugin/SpaceMouseUI`. See [technical notes](tools/c4d-plugin/README.txt)
and the archived [development history](docs/DEVELOPMENT_HISTORY.md).
Package a release with `python3 tools/c4d-plugin/package_release.py v0.1.0-preview.2`.

## License

[MIT](LICENSE). Cinema 4D and 3Dconnexion software, SDKs, frameworks, and binaries
retain their owners' licenses. This license does not grant redistribution rights
to those components. Install vendor software separately; it is not bundled.
