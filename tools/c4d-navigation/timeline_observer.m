#import <AppKit/AppKit.h>
#import <objc/message.h>
static id monitor;
static NSFileHandle *output;
static NSUInteger count;
__attribute__((visibility("default")))
void SMStartTimelineObserver(void) {
    dispatch_async(dispatch_get_main_queue(),^{
        if (monitor) return;
        NSString *path=@"/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-real-gestures.jsonl";
        [[NSFileManager defaultManager] createFileAtPath:path contents:nil attributes:nil];
        output=[NSFileHandle fileHandleForWritingAtPath:path];
        monitor=[NSEvent addLocalMonitorForEventsMatchingMask:(NSEventMaskScrollWheel|NSEventMaskMagnify) handler:^NSEvent *(NSEvent *event) {
            if (count>=2000 || ![event.window.title hasPrefix:@"Timeline"] || [NSStringFromClass(event.class) hasPrefix:@"SpaceMouse"]) return event;
            BOOL scroll=event.type==NSEventTypeScrollWheel;
            SEL deviceSelector=NSSelectorFromString(@"deviceID");
            NSInteger identity=[event respondsToSelector:deviceSelector] ? ((NSInteger(*)(id,SEL))objc_msgSend)(event,deviceSelector) : 0;
            NSDictionary *record=@{@"time":@(NSDate.date.timeIntervalSince1970),@"type":@(event.type),
                @"window":@(event.windowNumber),@"class":NSStringFromClass(event.class),@"device":@(identity),
                @"location":@[@(event.locationInWindow.x),@(event.locationInWindow.y)],
                @"flags":@(event.modifierFlags),@"phase":@(event.phase),@"momentum":@(event.momentumPhase),
                @"precise":@(scroll && event.hasPreciseScrollingDeltas),
                @"delta":scroll ? @[@(event.scrollingDeltaX),@(event.scrollingDeltaY)] : @[],
                @"magnification":scroll ? @0 : @(event.magnification)};
            NSData *json=[NSJSONSerialization dataWithJSONObject:record options:0 error:nil];
            [output writeData:json];[output writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
            count++;
            return event;
        }];
        [@"Passive Timeline gesture observer running" writeToFile:@"/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-observer-status.txt" atomically:YES encoding:NSUTF8StringEncoding error:nil];
    });
}
