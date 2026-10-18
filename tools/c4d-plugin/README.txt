SpaceMouse UI — experimental macOS C4D plugin preview

Cinema 4D 2027, macOS Apple Silicon. Requires the installed 3Dconnexion driver
and its 3DconnexionHelper. Keep the vendor C4D plugin installed for native 3D
viewport navigation. The separate SpaceMouse C4D Trial app must be quit; the
plugin pauses while it detects that app to prevent duplicate input.

The plugin shares the vendor plugin's existing driver connection and owns
its navigation timer inside Cinema 4D. A reversible, SDK-version-guarded
callback filter routes axis reports to panels while hovered, then forwards
all six unmodified axes to the vendor in the viewport. No second client is
registered and no driver activation/deactivation commands are used.
No companion app, IPC socket, Accessibility window inspection, or project
folder is used. Panel scroll events are dispatched locally to C4D's native views.
Native macOS Open/Save dialogs use continuous pixel scroll events through the
system input path while the dialog is active and the pointer is inside it.
For those dialogs, enable Cinema 4D under Privacy & Security > Device Control
and Data Access (called Accessibility on earlier macOS versions). Other panel
navigation does not require this permission. Driver profiles are unchanged.
Dialog scrolling starts automatically with the vendor connection, keeps the
accepted horizontal/vertical tuning, and restores its callback before shutdown.
Timeline navigation retains the accepted version-guarded direct view updates.
Timeline graph motion passes fractional deltas on every update. Horizontal view
ranges use reduced integral time fractions with microsecond precision. Vertical
Dope Sheet/track-list scrolling accumulates fractional pixels per live area and
gesture; F-Curve vertical pan/zoom retains native floating-point values. Existing
sensitivities, zoom response and complete drawing-cache refresh are unchanged.

Settings: Preferences > SpaceMouse UI (also opened by Extensions > SpaceMouse UI).
Independent horizontal/vertical/zoom sensitivity is available for Node graphs,
Dope Sheets, F-Curves, Timeline track lists, and lists/inspectors. Percentages
start at 100% of the accepted tuning. Changes apply immediately and persist.
The internal reference tuning incorporates the accepted Node pan 1.85/zoom .8,
Dope Sheet/F-Curve/track pan 3, list scroll 6, and overall zoom 6. All visible
sensitivity controls default to 100%; 200% doubles the corresponding calibrated
gain. Settings retain actual physical gains so loading the accepted preferences
does not change motion or repeatedly apply a migration on restart.
Navigation starts enabled. Existing
companion direction/zoom preferences migrate on first launch. Settings are stored under C4D's prefs/SpaceMouseUI directory. Routine navigation logging is disabled; failures are reported in the C4D Console.

This is an experimental prerelease tested only on macOS Apple Silicon.
Windows, Linux, Intel Macs, and other C4D versions have not been tested. The native
Timeline offsets and SDK callback adapter support the inspected C4D 2027
and installed 3DconnexionClient builds only. Registered Maxon
IDs: Settings Command 1071577, Input Service 1071578, Preferences 1071579.
The driver framework is referenced from its installed location, not bundled.

Build: python3 tools/c4d-plugin/build.py
Install: python3 tools/c4d-plugin/install.py <C4D user plugins folder>
Restart C4D after installing. The installer disables the old layout bridge
by renaming its .pyp file to .pyp.disabled, preserving it for recovery.

Fallback: quit C4D, remove the SpaceMouseUI plugin folder, rename the old
SpaceMouseLayoutTrial.pyp.disabled back to SpaceMouseLayoutTrial.pyp, then
start C4D and the preserved companion baseline. Keep the old project folder
for that fallback. Accepted baseline: baselines/automatic-timeline-2026-10-16.

If the native Preferences category is unavailable, Extensions > SpaceMouse UI opens a standalone grouped settings dialog. Changes apply immediately and save automatically. 100% preserves the accepted navigation feel.

3D viewport hover activation uses C4D active-view selection and the existing vendor Navlib motion reset. Continuous cross-view motion retains each camera orientation, with no explicit settling waits. Panel motion uses a 1% dead zone and linear response.

Node graph panning keeps screen speed constant across zoom levels, matching Blender's View2D conversion. Node events retain fractional pan/zoom deltas instead of accumulating whole-unit scroll ticks. Zoom input compensates for the inspected C4D scroll response to produce Blender-style reciprocal view-scale changes, retaining the previous small-motion gain. Zoom remains graph-centered; panel sensitivities still apply. These changes affect Node graphs only. A separate local scroll helper preserves the accepted vendor input connection. Unsupported builds retain the previous scroll-event route.


Component-mode stutter workaround: while SpaceMouse navigation is active in point/edge/polygon mode, unclicked mouse-move events inside the hovered 3D viewport are suppressed locally. Physical pointer movement, clicks and drags are untouched; hover processing resumes at rest. Toggle in Preferences > SpaceMouse UI > Prevent component-mode navigation stutter. Orthographic component hover is restored by the separate drawing compatibility correction described below.

Orthographic hover compatibility: the verified vendor PivotDraw callback reports failure for orthographic camera projections, stopping C4D's later drawing hooks. A per-document adapter calls the original callback and corrects that failed return for orthographic views. It follows open/new documents automatically, makes no vendor binary edits, and leaves navigation callbacks unchanged. Disable with Preferences > SpaceMouse UI > Restore orthographic component hover; disabling or stopping the runtime restores live instances. This correction has strict vendor/C4D build guards and skips unsupported builds. Its native adapter storage remains valid for the process lifetime so closed documents never leave dangling drawing callbacks.
