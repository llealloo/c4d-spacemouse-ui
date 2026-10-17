#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <objc/runtime.h>

@interface SMGesturePayload : NSObject
@property NSPoint location;
@property double magnification;
@property BOOL zoom;
@end
@implementation SMGesturePayload
@end
static char payloadKey;
static Class gestureClass;
static SMGesturePayload *payload(id event) { return objc_getAssociatedObject(event,&payloadKey); }
static NSInteger device(id event,SEL selector) { return 0x53504d; }
static CGFloat magnification(id event,SEL selector) { return payload(event).magnification; }
static NSPoint location(id event,SEL selector) { return payload(event).location; }
static NSEventType kind(id event,SEL selector) { return payload(event).zoom ? NSEventTypeMagnify : NSEventTypeScrollWheel; }

static NSEvent *makeEvent(NSWindow *window, NSPoint screen, double dx, double dy, NSInteger phase, BOOL zoom) {
    CGEventRef raw=CGEventCreateScrollWheelEvent(NULL,kCGScrollEventUnitPixel,2,(int32_t)llround(dy),(int32_t)llround(dx));
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventFixedPtDeltaAxis1,dy/10.0);
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventFixedPtDeltaAxis2,dx/10.0);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventScrollPhase,phase);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventMomentumPhase,0);
    CGEventSetIntegerValueField(raw,(CGEventField)51,window.windowNumber);
    CGEventSetFlags(raw,0);
    CGEventSetTimestamp(raw,(CGEventTimestamp)(NSProcessInfo.processInfo.systemUptime*1e9));
    CGEventSetLocation(raw,CGPointMake(screen.x,screen.y));
    NSEvent *event=[NSEvent eventWithCGEvent:raw];
    CFRelease(raw);
    if (!gestureClass) {
        gestureClass=objc_allocateClassPair(object_getClass(event),"SpaceMouseNativeTimelineEvent",0);
        class_addMethod(gestureClass,@selector(deviceID),(IMP)device,"q@:");
        class_addMethod(gestureClass,@selector(magnification),(IMP)magnification,"d@:");
        class_addMethod(gestureClass,@selector(locationInWindow),(IMP)location,"{CGPoint=dd}@:");
        class_addMethod(gestureClass,@selector(type),(IMP)kind,"Q@:");
        objc_registerClassPair(gestureClass);
    }
    SMGesturePayload *data=[SMGesturePayload new];
    CGFloat primaryHeight=NSScreen.screens.firstObject.frame.size.height;
    data.location=[window convertPointFromScreen:NSMakePoint(screen.x,primaryHeight-screen.y)];
    data.zoom=zoom;
    data.magnification=fmax(-.2,fmin(.2,dy*.002));
    objc_setAssociatedObject(event,&payloadKey,data,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    object_setClass(event,gestureClass);
    return event;
}

__attribute__((visibility("default")))
void SMTimelineDispatch(long windowID,double x,double y,double dx,double dy,long phase,int zoom) {
    // Retained by the dispatch block; all AppKit work happens after C4D's timer.
    dispatch_async(dispatch_get_main_queue(),^{
        @autoreleasepool {
            NSWindow *window=nil;
            for (NSWindow *candidate in NSApp.windows)
                if (candidate.windowNumber==windowID && [candidate.title hasPrefix:@"Timeline"]) { window=candidate; break; }
            if (!window) return;
            NSEvent *event=makeEvent(window,NSMakePoint(x,y),dx,dy,phase,zoom);
            NSView *view=window.contentView;
            NSEvent *hover=[NSEvent mouseEventWithType:NSEventTypeMouseMoved location:event.locationInWindow
                modifierFlags:0 timestamp:event.timestamp windowNumber:windowID context:nil eventNumber:0 clickCount:0 pressure:0];
            [view mouseMoved:hover];
            static NSMutableSet *registered;
            if (!registered) registered=[NSMutableSet new];
            if (![registered containsObject:@(windowID)]) {
                [view touchesBeganWithEvent:event];
                [registered addObject:@(windowID)];
            }
            if (zoom) [view magnifyWithEvent:event]; else [view scrollWheel:event];
            NSDictionary *report=@{@"time":@(NSDate.date.timeIntervalSince1970),@"window":@(windowID),
                @"location":@[@(event.locationInWindow.x),@(event.locationInWindow.y)],
                @"delta":@[@(event.scrollingDeltaX),@(event.scrollingDeltaY)],@"zoom":@(zoom),
                @"magnification":@(event.magnification),@"phase":@(event.phase)};
            static double lastLog;
            if (NSDate.date.timeIntervalSince1970-lastLog>1) {
                lastLog=NSDate.date.timeIntervalSince1970;
                [[NSJSONSerialization dataWithJSONObject:report options:0 error:nil]
                    writeToFile:@"/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-native.json" atomically:YES];
            }
        }
    });
}
