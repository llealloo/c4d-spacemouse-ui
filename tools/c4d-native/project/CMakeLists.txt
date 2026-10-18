set(target_base_name spacemouse.xpresso)
set(target_platforms macos)

set(target_settings [=[
{
  "apis" :
  [
    "cinema.framework",
    "cinema_hybrid.framework",
    "core.framework"
  ],
  "c4d" : true,
  "moduleid" : "local.spacemouse.xpresso",
  "stylecheck.level" : 0,
  "type" : "DLL"
}
]=])

set(enable_rtti OFF)
set(enable_exception_handling OFF)
set(source_directories source)
MaxonTargets_ProcessCinemaTargetVars()
