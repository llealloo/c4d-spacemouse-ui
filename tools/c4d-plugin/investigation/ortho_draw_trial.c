// Session-only, per-instance drawing adapter. Vendor code and input are unchanged.
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>

typedef bool (*DrawFn)(void*,void*,void*,void*,void*,void*,int);
typedef void *(*CameraFn)(void*,void*);
typedef void *(*EditorCameraFn)(void*);
typedef int (*ProjectionFn)(void*);
static DrawFn original_draw;
static CameraFn scene_camera;
static EditorCameraFn editor_camera;
static ProjectionFn camera_projection;
static uintptr_t *original_vtable, *trial_vtable;
static _Atomic unsigned long calls, corrected;
static _Atomic bool enabled;
static bool draw(void *self, void *node, void *doc, void *bd, void *bh, void *bt, int flags) {
    bool result = original_draw(self,node,doc,bd,bh,bt,flags);
    atomic_fetch_add(&calls,1);
    if (result || !atomic_load(&enabled) || !node || !doc || !bd || !bh) return result;
    void *camera = scene_camera(bd,doc);
    if (!camera) camera = editor_camera(bd);
    if (camera && camera_projection(camera) > 1) {
        atomic_fetch_add(&corrected,1);
        return true;
    }
    return result;
}
// Call on C4D main thread with drawing workers stopped. Single known class only.
int SMOrthoInstall(void *instance, uintptr_t expected_vtable, uintptr_t expected_draw,
                   void *get_scene_camera, void *get_editor_camera, void *get_projection) {
    if (!instance || !get_scene_camera || !get_editor_camera || !get_projection) return -1;
    uintptr_t current = atomic_load((_Atomic uintptr_t*)instance);
    if (trial_vtable && current == (uintptr_t)trial_vtable) return 1;
    if (current != expected_vtable || ((uintptr_t*)current)[27] != expected_draw) return -2;
    if (trial_vtable && original_vtable != (uintptr_t*)current) return -3;
    if (!trial_vtable) {
        uintptr_t *storage = malloc(34*sizeof(uintptr_t));
        if (!storage) return -4;
        memcpy(storage,(void*)(current-2*sizeof(uintptr_t)),34*sizeof(uintptr_t));
        original_vtable=(uintptr_t*)current;
        trial_vtable=storage+2;
        original_draw=(DrawFn)expected_draw;
        scene_camera=(CameraFn)get_scene_camera;
        editor_camera=(EditorCameraFn)get_editor_camera;
        camera_projection=(ProjectionFn)get_projection;
        trial_vtable[27]=(uintptr_t)&draw;
    }
    atomic_store(&enabled,true);
    atomic_store((_Atomic uintptr_t*)instance,(uintptr_t)trial_vtable);
    return 0;
}
int SMOrthoRestore(void *instance) {
    atomic_store(&enabled,false);
    if (!instance || !trial_vtable) return -1;
    uintptr_t expected=(uintptr_t)trial_vtable;
    return atomic_compare_exchange_strong((_Atomic uintptr_t*)instance,&expected,(uintptr_t)original_vtable)?0:-2;
}
void SMOrthoEnable(bool value) { atomic_store(&enabled,value); }
unsigned long SMOrthoCalls(void) { return atomic_load(&calls); }
unsigned long SMOrthoCorrected(void) { return atomic_load(&corrected); }
