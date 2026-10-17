#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
static CFMachPortRef tap;
static CFRunLoopSourceRef source;
static NSFileHandle *output;
static NSTimer *timer;
static CGEventRef observe(CGEventTapProxy proxy,CGEventType type,CGEventRef event,void *context){
 if(type==kCGEventTapDisabledByTimeout||type==kCGEventTapDisabledByUserInput){if(tap)CGEventTapEnable(tap,true);return event;}
 if(type!=kCGEventScrollWheel||!NSApp.active)return event;
 NSDictionary *row=@{@"time":@(NSProcessInfo.processInfo.systemUptime),@"pid":@(CGEventGetIntegerValueField(event,kCGEventSourceUnixProcessID)),@"x":@(CGEventGetDoubleValueField(event,kCGScrollWheelEventPointDeltaAxis2)),@"y":@(CGEventGetDoubleValueField(event,kCGScrollWheelEventPointDeltaAxis1)),@"fx":@(CGEventGetDoubleValueField(event,kCGScrollWheelEventFixedPtDeltaAxis2)),@"fy":@(CGEventGetDoubleValueField(event,kCGScrollWheelEventFixedPtDeltaAxis1)),@"lx":@(CGEventGetIntegerValueField(event,kCGScrollWheelEventDeltaAxis2)),@"ly":@(CGEventGetIntegerValueField(event,kCGScrollWheelEventDeltaAxis1)),@"phase":@(CGEventGetIntegerValueField(event,kCGScrollWheelEventScrollPhase)),@"momentum":@(CGEventGetIntegerValueField(event,kCGScrollWheelEventMomentumPhase)),@"continuous":@(CGEventGetIntegerValueField(event,kCGScrollWheelEventIsContinuous))};
 NSData *data=[NSJSONSerialization dataWithJSONObject:row options:0 error:nil];
 [output writeData:data];[output writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];return event;
}
__attribute__((visibility("default"))) void SMDialogProbeStop(void){
 [timer invalidate];timer=nil;
 if(tap){CGEventTapEnable(tap,false);if(source){CFRunLoopRemoveSource(CFRunLoopGetMain(),source,kCFRunLoopCommonModes);CFRunLoopRemoveSource(CFRunLoopGetMain(),source,(__bridge CFStringRef)NSModalPanelRunLoopMode);CFRelease(source);source=NULL;}CFRelease(tap);tap=NULL;}
 [output closeFile];output=nil;
}
__attribute__((visibility("default"))) int SMDialogProbeStart(const char *path){
 if(!NSThread.isMainThread)return -1;SMDialogProbeStop();
 tap=CGEventTapCreate(kCGSessionEventTap,kCGHeadInsertEventTap,kCGEventTapOptionListenOnly,CGEventMaskBit(kCGEventScrollWheel),observe,NULL);
 if(!tap)return -2;
 [NSFileManager.defaultManager createFileAtPath:@(path) contents:nil attributes:nil];output=[NSFileHandle fileHandleForWritingAtPath:@(path)];
 if(!output){SMDialogProbeStop();return -3;}
 source=CFMachPortCreateRunLoopSource(NULL,tap,0);CFRunLoopAddSource(CFRunLoopGetMain(),source,kCFRunLoopCommonModes);CFRunLoopAddSource(CFRunLoopGetMain(),source,(__bridge CFStringRef)NSModalPanelRunLoopMode);CGEventTapEnable(tap,true);
 timer=[NSTimer timerWithTimeInterval:180 repeats:NO block:^(NSTimer *unused){SMDialogProbeStop();}];[NSRunLoop.mainRunLoop addTimer:timer forMode:NSRunLoopCommonModes];[NSRunLoop.mainRunLoop addTimer:timer forMode:NSModalPanelRunLoopMode];return 0;
}
