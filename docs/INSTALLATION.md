# Installing SpaceMouse UI

## Compatibility and requirements

Only tested on **macOS Apple Silicon with Cinema 4D 2027**. This release contains
ARM64 macOS libraries. Windows, Linux, Intel Macs, and other Cinema 4D versions
have not been tested and are not supported by this build.

Install the official 3Dconnexion driver and Cinema 4D plugin, and keep
3DconnexionHelper running. SpaceMouse UI extends their navigation; it does not
replace them. Vendor files and driver profiles remain unmodified. Runtime
callback adapters are reversible and guarded for inspected builds; unsupported
builds may disable features and report the reason in Cinema 4D's Console.

This is an experimental preview using registered Maxon plugin IDs:
Settings Command `1071577`, Input Service `1071578`, Preferences `1071579`.
Native integration depends on inspected C4D and
3Dconnexion builds, so successful loading on every C4D 2027 installation is
not guaranteed. The orthographic-hover workaround currently expects C4D at
`/Applications/Maxon Cinema 4D 2027`.

## Installation

1. In Cinema 4D Preferences, use **Open Preferences Folder** to locate the active
   user preferences directory, then quit Cinema 4D.
2. Download `c4d-spacemouse-ui-v0.1.0-preview.2-macos-arm64.zip` from the GitHub
   release and extract it. Use the plugin ZIP, rather than GitHub's source archives.
3. Create a `plugins` folder in the preferences directory if needed. Copy the
   extracted `SpaceMouseUI` folder into it. The resulting path should be
   `plugins/SpaceMouseUI/SpaceMouseUI.pyp`, without an extra nested folder.
4. Restart Cinema 4D. Settings appear under **Preferences > SpaceMouse UI**;
   **Extensions > SpaceMouse UI** also opens settings. Navigation starts enabled.

No compiler, Python installation, or companion application is needed for the
prebuilt plugin. Keep the official 3Dconnexion plugin and driver installed.

## Permissions and use

For native Open/Save dialog scrolling, enable Cinema 4D under macOS
**System Settings > Privacy & Security > Accessibility** (called **Device Control
and Data Access** on some versions). Other panel navigation does not require
this permission. Quit the earlier **SpaceMouse C4D Trial** companion app if it
is installed, to avoid duplicate input.

Point at a supported panel to navigate it; point at a 3D viewport to use normal
3Dconnexion navigation. Sensitivity controls are independent per panel type;
100% uses the plugin's default calibration. Preferences persist in the Cinema 4D
preferences directory under `SpaceMouseUI`.

The libraries are locally ad-hoc signed, not Developer ID signed or notarized.
If macOS blocks loading them, review the message in Privacy & Security and the
Cinema 4D Console. Do not disable Gatekeeper globally.

## Upgrade or remove

Quit Cinema 4D before changing plugin files. Back up and replace the entire
existing `SpaceMouseUI` plugin folder when upgrading; do not merge old and new
files. To uninstall, remove that folder and restart Cinema 4D. The official
3Dconnexion plugin and driver remain installed.

If upgrading from the local layout-bridge trials, disable the old
`SpaceMouseLayoutTrial.pyp` by renaming it to `SpaceMouseLayoutTrial.pyp.disabled`
while Cinema 4D is closed. Preserve it for recovery. Do not run the old trial
and this plugin together.

## Licenses

SpaceMouse UI source and its compiled helpers are distributed under the included
MIT license. Cinema 4D and 3Dconnexion components retain their own licenses and
are not included in this download.
