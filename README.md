# SpaceMouse UI for Cinema 4D

A macOS development plugin that extends SpaceMouse navigation to Cinema 4D's
Node Editor, Timeline, lists, inspectors, and native Open/Save dialogs while
preserving the 3Dconnexion plugin's viewport navigation.

## Requirements

- Cinema 4D 2027 on macOS Apple Silicon; compatibility is limited to the inspected builds.
- Installed 3Dconnexion driver, running 3DconnexionHelper, and the vendor Cinema 4D plugin.
- Xcode Command Line Tools (`clang`, `codesign`) and Python 3 to build.
- The installed `3DconnexionClient.framework` at `/Library/Frameworks`.

## Build and install

From the repository root:

```sh
python3 tools/c4d-plugin/build.py
```

The built plugin is written to `.build/plugin/SpaceMouseUI`. Quit Cinema 4D,
then install into your Cinema 4D user plugins directory:

```sh
python3 tools/c4d-plugin/install.py "/path/to/Cinema 4D/user/plugins"
```

Restart Cinema 4D. Settings are available under **Preferences > SpaceMouse UI**
and **Extensions > SpaceMouse UI**. Quit the separate SpaceMouse C4D Trial
companion app before using this plugin.

See [the plugin notes](tools/c4d-plugin/README.txt) for navigation behavior,
permissions, compatibility guards, and recovery instructions.

## Project layout

- `tools/c4d-plugin/`: plugin entry point, Python runtime, native helpers, build/install scripts, and tests.
- `tools/c4d-navigation/`: shared Timeline/view code and the earlier companion prototype.
- `Sources/SpaceMouseProbe/`: earlier standalone Swift HID diagnostic tool.
- `.build/`: generated output, excluded from Git.

Local baseline snapshots, reference files, and research captures are excluded
from Git. Historical notes below may refer to those local files.

## Development status

This is a development preview. Native offsets and callback adapters are specific
to inspected Cinema 4D and 3Dconnexion builds. Temporary plugin IDs need assigned
Maxon IDs before distribution. The 3Dconnexion framework is linked from its
installed location and is not bundled.

## License

This project's original source code is licensed under the [MIT License](LICENSE).

Cinema 4D and 3Dconnexion software, SDKs, frameworks, and binaries remain subject
to their respective owners' licenses. This project's MIT license does not grant
rights to those third-party components or permission to redistribute them.
Install the required vendor software separately; the 3Dconnexion framework is
not bundled with this plugin.

## Earlier prototype notes

# SpaceMouse macOS probe

This is the first diagnostic prototype for a native macOS SpaceMouse input
translator. It reads the physical SpaceMouse through IOKit without using the
3Dconnexion SDK.

The tool is non-invasive by default: it prints the six HID axes and buttons but
does not inject events or take exclusive control of the device.

## Build

```sh
swift build
```

## Safe first run

The packaged driver currently opens the SpaceMouse exclusively. Quit
`3DconnexionHelper` before running the direct-HID probe; otherwise the tool will
report `kIOReturnExclusiveAccess`.

```sh
swift run spacemouse-probe
```

Move the cap along each axis and confirm the reported orientation and range.
Press Control-C to stop.

To capture the packaged driver's scroll events for comparison:

```sh
swift run spacemouse-probe --observe-scroll
```

macOS will request Input Monitoring permission. After granting it, quit and
rerun the command. For this mode, leave `3DconnexionHelper` running. The probe
will continue in scroll-observer-only mode when the packaged driver holds HID
access, allowing its generated events to be measured.

## Experimental smooth scrolling

With `3DconnexionHelper` still quit, run:

```sh
swift run spacemouse-probe --smooth-scroll --seize
```

This mode requests Accessibility permission and posts continuous, pixel-based
two-axis scroll events. The defaults map cap X to horizontal scrolling and cap
Z to vertical scrolling, matching the SpaceMouse's pan right/left and pan
up/down translation axes. To override that mapping, use:

```sh
swift run spacemouse-probe --smooth-scroll --seize --vertical-axis y
```

Useful tuning flags include `--invert-x`, `--invert-y`, `--max-speed`,
`--dead-zone`, and `--curve`. Run `swift run spacemouse-probe --help` for the
complete list.

Finder can interpret phase-aware horizontal scrolls as navigation swipes. Use
`--legacy-scroll` to retain precise pixel scrolling without gesture phases when
testing that behavior globally. Without the flag, the probe automatically uses
legacy continuous events only in Finder and retains native gesture phases in
Safari, Firefox, and other applications.

## Current scope

- Direct six-axis and button input through public IOKit APIs.
- Inspection of real scroll-event precision, phase, and momentum fields.
- Opt-in continuous two-axis pixel scrolling.
- No synthetic momentum and no private APIs.
- No pinch/magnify injection yet; macOS has no public system-wide magnify-event
  constructor equivalent to its public scroll-event API.

## Cinema 4D node navigation experiment

`tools/c4d-navigation/main.m` is a separate, reversible companion prototype.
It uses the installed 3Dconnexion SDK while leaving the normal driver running.
Build it with `zsh tools/c4d-navigation/build.sh`, then open
`.build/SpaceMouse C4D Trial.app`. It starts paused.

The trial needs macOS Accessibility permission. Because it is locally ad-hoc
signed, rebuilding can invalidate an existing permission entry; remove and
re-add the app if its switch is on but the prototype still reports denial.

Start the trial, open Cinema 4D's **floating Node Editor**, and put the pointer
in the **left half of the graph**, below the toolbar. Cap X/Z generate precise
pixel-based pan input with gesture phases at a nominal 120 Hz. Docked panels
are not supported yet. Y-axis zoom uses Control+scroll, defaults on, and can be
toggled in the SM Trial menu. Pan and zoom now emit independently so they can
operate together. The user confirmed both work together after modifier isolation
was fixed. Zoom sensitivity defaults to 2x the initial trial's value and can be
adjusted live from 0.5x to 8x in SM Trial → Zoom sensitivity; the choice persists.
SpaceMouse zoom events now target the graph center, independently of the pointer,
with no mouse-centered mode. In this trial, graph bounds assume the standard
floating Node Editor layout (graph on the left, inspector on the right); moving
the divider or hiding the inspector is not yet accounted for.
Navigation events are delivered directly to the Cinema 4D process. The initial
centered-zoom build used the system HID stream, which also relocated the cursor;
the user confirmed direct delivery works and the physical pointer stays put.
Throttling diagnostics to once per second improved perceived refresh. A slight
stepping effect remains during combined pan/zoom. The accepted app and source
are preserved in `baselines/node-editor-2026-10-15/`.
Horizontal and vertical pan inversion can be changed live in the SM Trial menu;
those settings persist. Vertical inversion defaults on following the first trial.

Use Start/Pause or Quit to release the device. Smoothness, axis calibration,
zoom behavior, and restoration of normal 3D navigation require live validation.
The event-construction checks and non-activating driver-registration check have
passed. In the initial live trials, the user reported smooth node panning,
smooth zoom in the separate-mode build, correct vertical direction after
inversion, and working 3D navigation after leaving the editor.
Full Blender-equivalent behavior remains a separate acceptance target.

Investigation details and binary evidence are in `research/c4d/findings.txt`.

## Expanded panel trial

The development build additionally recognizes floating `Objects` and `Attributes`
windows, including numbered copies such as `Objects (2)`. Open these from Window
→ Object Manager / Attribute Manager. Objects uses X/Z continuous scrolling;
Attributes uses Z vertical scrolling, addressed to the blank left margin to avoid
scrolling over numeric controls. Y-axis zoom is disabled in these list panels.
Their smoothness and restoration of viewport navigation still require live tests.
Docked panels, other managers, timelines, and alternate/localized titles are not
supported yet. Cinema 4D exposes no internal manager children in the inspected
Accessibility tree, so docked-panel discovery needs additional work rather than
assuming that every region of the main window is safe to scroll.

### Calibrated docked Objects trial

`tools/c4d-navigation/panel-regions.json` defines window-relative rectangles for
managers inside the main window. The initial Objects rectangle was calibrated
from the user's current 3200×1770 main window. Only that size is accepted; moving
the main window is supported. Resizing, changing layouts, changing tabs, or moving
dividers requires recalibration. This is not automatic panel recognition.
The file reloads once per second without recompilation or permission refresh.
Outside the configured rectangle the trial releases the SpaceMouse to the normal
3D driver. The current rectangle deliberately excludes the panel edges and header.
Floating test windows were minimized to expose the main window; they can be
restored from the Dock. The accepted Node Editor baseline remains unchanged.

The user has now confirmed docked Objects, docked Attributes, and normal 3D
navigation all work in the calibrated layout. Both docked managers use normal
pointer-based continuous scrolling. Attributes currently shares the Objects
route (two-axis scroll, no zoom); numeric-field hover behavior is unverified.
The accepted snapshot is `baselines/docked-objects-attributes-2026-10-15/`.

## Live layout trial (current development build)

Main-window routing now replaces calibrated manager rectangles with live viewport
exclusion. `layout_bridge.py` runs inside C4D and publishes native
`BaseDraw.GetFrameScreen()` bounds every 80 ms. The companion checks the pointer
against those bounds each tick: viewports retain normal driver navigation; other
main-window content receives continuous pointer-based scrolling. This does not
identify individual manager types or provide centered zoom in docked node graphs.
Main toolbar/footer and viewport borders/headers are excluded conservatively.

The session bridge is currently a visible **SpaceMouse Live Layout** dialog.
Keep it open. Stale/missing bounds pause main-window scrolling after 300 ms;
there is no fallback to the old static rectangles. Main-window moves, resizes,
and rearrangements should follow native bounds but await live acceptance.
The existing floating Node Editor path remains unchanged.

The bridge can be restarted from C4D's Python console with:

```python
exec(compile(open('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/layout_bridge.py').read(), 'layout_bridge.py', 'exec'))
```

This is session-only and does not yet auto-start after restarting Cinema 4D.
Close its dialog or click Stop layout tracking to stop it. It reads viewport
geometry and writes a local heartbeat; it does not modify documents or layouts.

### Full floating Node Editor graph and inspector (development)

The updated bridge also reports the floating Node Editor graph's native view
bounds. The companion uses the full graph for pan/centered zoom and normal
pointer-based scrolling over its inspector, rather than the former left-half
activation region. Graph/inspector transitions are checked every tick. The graph
view is identified by native MaxonView geometry; this remains a version-sensitive
heuristic. It follows current divider geometry without a fixed ratio. Node mode
now also needs the live layout bridge; stale geometry disables output.
Live full-graph/inspector acceptance is pending.

### Background layout service (installed prototype)

`layout_service.pyp` is now installed as `SpaceMouseLayoutTrial.pyp` in Cinema
4D 2027's user plugins folder. It loads at C4D startup and publishes geometry
without a dialog. Startup, Model→Standard layout switching, and detection of a
newly opened Node Editor were verified with fresh snapshots after restart.
The old SpaceMouse Live Layout dialog is no longer required; companion text
still mentions it because its signed binary was intentionally left unchanged.
The companion app itself remains necessary and must be started separately.
The service currently references helper source in this project, so keep the
project in place. This is a development install with a collision-checked test
plugin ID, not a distributable package.

### Floating animation-panel scrolling trial

Floating `Timeline` / `Timeline (...)` windows, including Dope Sheet and F-Curve
modes, now receive continuous X/Z scrolling at the physical pointer. Cinema 4D
routes the input to its nested regions. Docked animation panels use the existing
main-window scroll route. Native smoothness, horizontal pan behavior, and nested
routing await live testing; timeline zoom is not implemented yet. This is the
first scrolling stage, not completed Blender-equivalent animation navigation.

### Experimental native Timeline gestures

The current floating Timeline build sends X/Z pan and Y zoom to a local Unix
socket consumed inside C4D. The message plugin polls input at a requested8ms
interval while publishing geometry at80ms. It delivers touch-classified scroll
and magnify events directly to the native Timeline view, with an owned synthetic
NSEvent subclass supplying gesture identity/magnification. This is experimental
and uses version-sensitive native behavior. It does not hold mouse buttons,
post global mouse movement, or edit animation data.

Packet delivery and zero-delta native pan/magnify dispatch are verified. Actual
pan directions, uniform zoom, simultaneous movement, and nested-region behavior
still need live acceptance. Docked Timeline special mapping is not implemented;
it continues through generic main-window scrolling. Existing accepted baselines
are preserved. The current session transport is already active; future C4D
starts load it from the updated layout-service plugin.
