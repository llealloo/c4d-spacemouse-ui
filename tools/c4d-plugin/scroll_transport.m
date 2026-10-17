// Local Node Editor scroll transport with fractional AppKit deltas.
// No driver registration, system event posting, or cursor movement.
#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <objc/runtime.h>
#import <math.h>
@interface SMPreciseScrollPayload : NSObject
@property NSPoint point;
@property double dx;
@property double dy;
@end
@implementation SMPreciseScrollPayload
@end
static char payloadKey;
static SMPreciseScrollPayload *payload(id event) { return objc_getAssociatedObject(event,&payloadKey); }
static NSPoint location(id event,SEL selector) { return payload(event).point; }
static double scrollX(id event,SEL selector) { return payload(event).dx; }
static double scrollY(id event,SEL selector) { return payload(event).dy; }
static double legacyX(id event,SEL selector) { return payload(event).dx/10.0; }
static double legacyY(id event,SEL selector) { return payload(event).dy/10.0; }
static BOOL precise(id event,SEL selector) { return YES; }
static NSEvent *makeScroll(NSWindow *window,NSPoint screen,double dx,double dy,int phase,BOOL zoom) {
    CGEventRef raw=CGEventCreateScrollWheelEvent(NULL,kCGScrollEventUnitPixel,2,(int32_t)llround(dy),(int32_t)llround(dx));
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventFixedPtDeltaAxis1,dy/10.0);
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventFixedPtDeltaAxis2,dx/10.0);
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventPointDeltaAxis1,dy);
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventPointDeltaAxis2,dx);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventIsContinuous,1);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventScrollPhase,phase);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventMomentumPhase,0);
    CGEventSetIntegerValueField(raw,(CGEventField)51,window.windowNumber);
    CGEventSetFlags(raw,zoom?kCGEventFlagMaskControl:0);
    CGEventSetTimestamp(raw,(uint64_t)(NSProcessInfo.processInfo.systemUptime*1e9));
    CGEventSetLocation(raw,NSPointToCGPoint(screen));
    NSEvent *event=[NSEvent eventWithCGEvent:raw];CFRelease(raw);
    static Class eventClass;static dispatch_once_t once;
    dispatch_once(&once,^{
        eventClass=objc_allocateClassPair(object_getClass(event),"SpaceMouseUIPreciseScrollEventV1",0);
        class_addMethod(eventClass,@selector(locationInWindow),(IMP)location,"{CGPoint=dd}@:");
        class_addMethod(eventClass,@selector(scrollingDeltaX),(IMP)scrollX,"d@:");
        class_addMethod(eventClass,@selector(scrollingDeltaY),(IMP)scrollY,"d@:");
        class_addMethod(eventClass,@selector(deltaX),(IMP)legacyX,"d@:");
        class_addMethod(eventClass,@selector(deltaY),(IMP)legacyY,"d@:");
        class_addMethod(eventClass,@selector(hasPreciseScrollingDeltas),(IMP)precise,"B@:");
        objc_registerClassPair(eventClass);
    });
    SMPreciseScrollPayload *data=[SMPreciseScrollPayload new];
    data.point=[window convertPointFromScreen:NSMakePoint(screen.x,NSScreen.screens.firstObject.frame.size.height-screen.y)];
    data.dx=dx;data.dy=dy;
    objc_setAssociatedObject(event,&payloadKey,data,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(event,eventClass);
    return event;
}
__attribute__((visibility("default"))) int SMPreciseScroll(int64_t windowID,double x,double y,double dx,double dy,int phase,int zoom) {
    if(!NSThread.isMainThread || !NSApp.active || !isfinite(dx) || !isfinite(dy))return 0;
    NSWindow *window=nil;
    for(NSWindow *candidate in NSApp.windows)if(candidate.windowNumber==windowID && candidate.visible){window=candidate;break;}
    if(!window)return 0;
    NSEvent *event=makeScroll(window,NSMakePoint(x,y),dx,dy,phase,zoom);
    NSEvent *hover=[NSEvent mouseEventWithType:NSEventTypeMouseMoved location:event.locationInWindow modifierFlags:0 timestamp:event.timestamp windowNumber:windowID context:nil eventNumber:0 clickCount:0 pressure:0];
    NSView *view=[window.contentView hitTest:event.locationInWindow];Class maxon=NSClassFromString(@"MaxonView");
    while(view && maxon && ![view isKindOfClass:maxon])view=view.superview;
    if(!view)view=window.contentView;
    [view mouseMoved:hover];[view scrollWheel:event];return 1;
}
