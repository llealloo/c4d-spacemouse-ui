#import <AppKit/AppKit.h>
#include <stdatomic.h>
static id monitor;
static BOOL enabled;
static NSInteger targetWindow;
static NSRect area;
static uint64_t suppressed;
static double updated;
static NSEvent *lastSuppressed;
static uint64_t resumed;
void SMHoverGateSet(int active,long long window,double x,double y,double w,double h) {
    BOOL release=enabled && !active;
    updated=NSProcessInfo.processInfo.systemUptime;enabled=active;targetWindow=window;area=NSMakeRect(x,y,w,h);
    if(release && lastSuppressed){
        NSEvent *old=lastSuppressed;lastSuppressed=nil;
        NSWindow *host=old.window;
        if(host && NSApp.active && !NSEvent.pressedMouseButtons){
            NSPoint point=[host convertPointFromScreen:NSEvent.mouseLocation];
            NSEvent *refresh=[NSEvent mouseEventWithType:NSEventTypeMouseMoved location:point
                modifierFlags:NSEvent.modifierFlags timestamp:updated windowNumber:host.windowNumber
                context:nil eventNumber:0 clickCount:0 pressure:0];
            [NSApp postEvent:refresh atStart:NO];++resumed;
        }
    }
}
void SMHoverGateStart(void) {
    if(monitor)return;
    monitor=[NSEvent addLocalMonitorForEventsMatchingMask:NSEventMaskMouseMoved handler:^NSEvent*(NSEvent*event){
        if(!enabled || NSProcessInfo.processInfo.systemUptime-updated>.1 || event.windowNumber!=targetWindow || NSEvent.pressedMouseButtons)return event;
        NSPoint pointer=NSEvent.mouseLocation;
        CGFloat height=NSScreen.screens.firstObject.frame.size.height;
        pointer.y=height-pointer.y;
        if(NSPointInRect(pointer,area)){lastSuppressed=event;++suppressed;return nil;}
        return event;
    }];
}
void SMHoverGateStop(void){enabled=NO;if(monitor){[NSEvent removeMonitor:monitor];monitor=nil;}}
uint64_t SMHoverGateCount(void){return suppressed;}
uint64_t SMHoverGateResumeCount(void){return resumed;}
int SMHoverGateEnabled(void){return enabled;}
