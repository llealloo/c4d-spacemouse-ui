#import <AppKit/AppKit.h>
// Local hover suppression only; physical pointer and button events are untouched.
static id monitor;
static BOOL enabled;
static NSInteger targetWindow;
static NSRect area;
static uint64_t suppressed;
static double updated;
void SMHoverGateSet(int active,long long window,double x,double y,double w,double h) {
    updated=NSProcessInfo.processInfo.systemUptime;enabled=active;targetWindow=window;area=NSMakeRect(x,y,w,h);
}
void SMHoverGateStart(void) {
    if(monitor)return;
    monitor=[NSEvent addLocalMonitorForEventsMatchingMask:NSEventMaskMouseMoved handler:^NSEvent*(NSEvent*event){
        if(!enabled || NSProcessInfo.processInfo.systemUptime-updated>.1 || event.windowNumber!=targetWindow || NSEvent.pressedMouseButtons)return event;
        NSPoint pointer=NSEvent.mouseLocation;
        CGFloat height=NSScreen.screens.firstObject.frame.size.height;
        pointer.y=height-pointer.y;
        if(NSPointInRect(pointer,area)){++suppressed;return nil;}
        return event;
    }];
}
void SMHoverGateStop(void){enabled=NO;if(monitor){[NSEvent removeMonitor:monitor];monitor=nil;}}
uint64_t SMHoverGateCount(void){return suppressed;}
int SMHoverGateEnabled(void){return enabled;}
