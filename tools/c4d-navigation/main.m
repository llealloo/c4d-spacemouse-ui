#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <ConnexionClientAPI.h>
#include <math.h>
#include <signal.h>
#include <dlfcn.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <fcntl.h>
#include <unistd.h>

// A reversible feasibility probe. No modifications to Cinema 4D or its plug-in.
static const int64_t EventTag = 0x53504d4344340001;
static uint16_t clientID;
static double axes[6], lastInput;
static NSUInteger inputCount;
// The SDK retains the identity of its registration thread. A serial GCD queue
// does not guarantee that identity across calls; keep one NSThread alive instead.
@interface SDKWorker : NSObject
@property NSThread *thread;
- (void)run;
- (void)execute:(dispatch_block_t)block;
@end
@implementation SDKWorker
- (void)run {
    @autoreleasepool {
        NSRunLoop *loop = NSRunLoop.currentRunLoop;
        [loop addPort:[NSMachPort port] forMode:NSDefaultRunLoopMode];
        while (YES) @autoreleasepool { [loop runMode:NSDefaultRunLoopMode beforeDate:NSDate.distantFuture]; }
    }
}
- (void)execute:(dispatch_block_t)block { @autoreleasepool { block(); } }
@end
static void SDKAsync(dispatch_block_t block) {
    static SDKWorker *worker;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        worker = [SDKWorker new];
        worker.thread = [[NSThread alloc] initWithTarget:worker selector:@selector(run) object:nil];
        worker.thread.name = @"SpaceMouse SDK lifecycle";
        [worker.thread start];
    });
    [worker performSelector:@selector(execute:) onThread:worker.thread withObject:[block copy] waitUntilDone:NO];
}

static double response(double value) {
    double magnitude = fmin(fabs(value) / 350.0, 1.0);
    if (magnitude <= 0.04) return 0;
    return copysign(pow((magnitude - 0.04) / 0.96, 1.5), value);
}

static void receive(unsigned int device, unsigned int message, void *argument) {
    if (message != kConnexionMsgDeviceState || !argument) return;
    const ConnexionDeviceState state = *(const ConnexionDeviceState *)argument;
    dispatch_async(dispatch_get_main_queue(), ^{
        if (state.client != clientID || state.command != kConnexionCmdHandleAxis) return;
        for (int i = 0; i < 6; ++i) axes[i] = state.axis[i];
        lastInput = NSProcessInfo.processInfo.systemUptime;
        ++inputCount;
    });
}

static CGEventRef makeScroll(double dx, double dy, int64_t phase, BOOL zoom) {
    CGEventRef event = CGEventCreateScrollWheelEvent(NULL, kCGScrollEventUnitPixel,
                                                    2, (int32_t)llround(dy), (int32_t)llround(dx));
    // Keep fractional fixed-point deltas as well as integral pixel deltas. Never
    // turn the cap into wheel clicks. Applications choose which fields to read.
    CGEventSetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis1, dy / 10.0);
    CGEventSetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis2, dx / 10.0);
    CGEventSetIntegerValueField(event, kCGScrollWheelEventIsContinuous, 1);
    CGEventSetIntegerValueField(event, kCGScrollWheelEventScrollPhase, phase);
    CGEventSetIntegerValueField(event, kCGScrollWheelEventMomentumPhase, 0);
    CGEventSetIntegerValueField(event, kCGEventSourceUserData, EventTag);
    // Maxon documents control-scroll as its magnify input. Keep the modifier
    // local to this event; never synthesize physical Control key presses.
    CGEventSetFlags(event, zoom ? kCGEventFlagMaskControl : 0);
    return event;
}

static void anchorZoom(CGEventRef event, BOOL zoom, CGPoint graphCenter) {
    // Scroll-event location supplies the zoom pivot. Deliver this event directly
    // to C4D: posting it through the HID stream also relocates the system cursor.
    if (zoom) CGEventSetLocation(event, graphCenter);
}

static void addressWindow(CGEventRef event, pid_t pid, CGWindowID windowID) {
    CGEventSetIntegerValueField(event, kCGEventTargetUnixProcessID, pid);
    CGEventSetIntegerValueField(event, kCGMouseEventWindowUnderMousePointer, windowID);
    CGEventSetIntegerValueField(event, kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent, windowID);
}

static CGEventRef makeTracking(CGPoint screen, CGPoint local, CGWindowID windowID, pid_t pid) {
    // The public NSEvent factory carries AppKit's window number; a bare Quartz
    // MouseMoved lacks that routing metadata when posted to a process queue.
    NSEvent *tracking = [NSEvent mouseEventWithType:NSEventTypeMouseMoved
        location:NSPointFromCGPoint(local) modifierFlags:0
        timestamp:NSProcessInfo.processInfo.systemUptime windowNumber:windowID
        context:nil eventNumber:0 clickCount:0 pressure:0];
    CGEventRef event = CGEventCreateCopy(tracking.CGEvent);
    CGEventSetLocation(event, screen);
    addressWindow(event, pid, windowID);
    CGEventSetFlags(event, 0);
    CGEventSetIntegerValueField(event, kCGEventSourceUserData, EventTag);
    return event;
}

static void setWindowLocation(CGEventRef event, CGPoint local) {
    // App-directed Quartz scrolling needs a window-local position in addition
    // to the screen point. This exported SPI is optional and version-sensitive.
    typedef void (*WindowLocationSetter)(CGEventRef, CGPoint);
    static WindowLocationSetter setter;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ setter = (WindowLocationSetter)dlsym(RTLD_DEFAULT, "CGEventSetWindowLocation"); });
    if (setter) setter(event, local);
}

static CGWindowID findWindowID(pid_t pid, CGRect frame) {
    NSArray *windows = CFBridgingRelease(CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID));
    for (NSDictionary *window in windows) {
        if ([window[(__bridge NSString *)kCGWindowOwnerPID] intValue] != pid ||
            [window[(__bridge NSString *)kCGWindowLayer] intValue] != 0) continue;
        CGRect bounds;
        if (!CGRectMakeWithDictionaryRepresentation((__bridge CFDictionaryRef)
            window[(__bridge NSString *)kCGWindowBounds], &bounds)) continue;
        if (fabs(bounds.origin.x - frame.origin.x) < 3 && fabs(bounds.origin.y - frame.origin.y) < 3 &&
            fabs(bounds.size.width - frame.size.width) < 3 && fabs(bounds.size.height - frame.size.height) < 3)
            return [window[(__bridge NSString *)kCGWindowNumber] unsignedIntValue];
    }
    return kCGNullWindowID;
}

// Resolve the actual focused AX window rather than rediscovering it through
// the separately filtered Quartz window list. Optional, version-sensitive SPI;
// it uses the same Accessibility permission already required by this trial.
static CGWindowID focusedWindowID(AXUIElementRef window, pid_t pid, CGRect frame) {
    typedef AXError (*WindowGetter)(AXUIElementRef, CGWindowID *);
    static WindowGetter getter;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ getter = (WindowGetter)dlsym(RTLD_DEFAULT, "_AXUIElementGetWindow"); });
    CGWindowID windowID = kCGNullWindowID;
    if (getter && getter(window, &windowID) == kAXErrorSuccess && windowID) return windowID;
    return findWindowID(pid, frame);
}

static id attribute(AXUIElementRef element, CFStringRef key) {
    CFTypeRef value = NULL;
    if (AXUIElementCopyAttributeValue(element, key, &value) != kAXErrorSuccess) return nil;
    return CFBridgingRelease(value);
}

@interface Probe : NSObject <NSApplicationDelegate>
@property NSStatusItem *item;
@property NSWindow *window;
@property NSTextField *statusLabel;
@property NSMenuItem *toggleItem, *statusItem, *zoomItem;
@property NSMenuItem *invertXItem, *invertYItem;
@property NSMenuItem *zoomGainItem;
@property NSTimer *timer;
@property BOOL enabled, starting, claimed, gesture, zoomGesture, zoomEnabled, terminating;
@property BOOL invertX, invertY;
@property double lastTick, lastContext, lastLog, remainderX, remainderY;
@property double zoomRemainder;
@property double zoomGain;
@property pid_t targetPID;
@property NSString *contextReason;
@property BOOL listPanel, verticalOnly, dockedPanel, mainWindowContext, nodeWindowContext;
@property CGRect nodeGraphRect;
@property BOOL timelineContext;
@property NSArray<NSDictionary *> *liveTimelines;
@property CGWindowID targetWindowID;
@property CGRect graphRect;
@property NSArray<NSValue *> *liveViewports;
@property double layoutTimestamp;
@property CGPoint zoomCenter;
@property CGRect targetWindowFrame;
@end

@implementation Probe
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    [NSUserDefaults.standardUserDefaults registerDefaults:@{@"invertVertical": @YES, @"zoomEnabled": @YES, @"zoomGain": @2.0}];
    self.invertX = [NSUserDefaults.standardUserDefaults boolForKey:@"invertHorizontal"];
    self.invertY = [NSUserDefaults.standardUserDefaults boolForKey:@"invertVertical"];
    self.zoomEnabled = [NSUserDefaults.standardUserDefaults boolForKey:@"zoomEnabled"];
    self.zoomGain = [NSUserDefaults.standardUserDefaults doubleForKey:@"zoomGain"];
    if (!isfinite(self.zoomGain) || self.zoomGain < 0.25 || self.zoomGain > 8) self.zoomGain = 2;
    self.item = [NSStatusBar.systemStatusBar statusItemWithLength:NSVariableStatusItemLength];
    self.item.button.title = @"SM Trial";
    NSMenu *menu = [NSMenu new];
    self.statusItem = [menu addItemWithTitle:@"Paused" action:nil keyEquivalent:@""];
    self.toggleItem = [menu addItemWithTitle:@"Start smooth navigation trial" action:@selector(toggle:) keyEquivalent:@""];
    self.toggleItem.target = self;
    self.zoomItem = [menu addItemWithTitle:@"Experimental Y-axis zoom" action:@selector(toggleZoom:) keyEquivalent:@""];
    self.zoomItem.target = self;
    self.zoomItem.state = self.zoomEnabled ? NSControlStateValueOn : NSControlStateValueOff;
    self.zoomGainItem = [menu addItemWithTitle:[NSString stringWithFormat:@"Zoom sensitivity: %gx", self.zoomGain] action:nil keyEquivalent:@""];
    NSMenu *gainMenu = [NSMenu new];
    for (NSNumber *gain in @[@0.5, @1.0, @1.5, @2.0, @3.0, @4.0, @6.0, @8.0]) {
        NSMenuItem *choice = [gainMenu addItemWithTitle:[NSString stringWithFormat:@"%gx", gain.doubleValue]
                                               action:@selector(selectZoomGain:) keyEquivalent:@""];
        choice.target = self;
        choice.representedObject = gain;
        choice.state = fabs(self.zoomGain - gain.doubleValue) < 0.001 ? NSControlStateValueOn : NSControlStateValueOff;
    }
    self.zoomGainItem.submenu = gainMenu;
    self.invertXItem = [menu addItemWithTitle:@"Invert horizontal pan" action:@selector(toggleInvertX:) keyEquivalent:@""];
    self.invertXItem.target = self;
    self.invertXItem.state = self.invertX ? NSControlStateValueOn : NSControlStateValueOff;
    self.invertYItem = [menu addItemWithTitle:@"Invert vertical pan" action:@selector(toggleInvertY:) keyEquivalent:@""];
    self.invertYItem.target = self;
    self.invertYItem.state = self.invertY ? NSControlStateValueOn : NSControlStateValueOff;
    NSMenuItem *permissions = [menu addItemWithTitle:@"Check Accessibility permission…" action:@selector(permissions:) keyEquivalent:@""];
    permissions.target = self;
    [menu addItem:NSMenuItem.separatorItem];
    NSMenuItem *quit = [menu addItemWithTitle:@"Quit and restore normal navigation" action:@selector(quit:) keyEquivalent:@"q"];
    quit.target = self;
    self.item.menu = menu;
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(200, 200, 580, 260)
                                             styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable
                                               backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"SpaceMouse C4D Trial";
    self.window.releasedWhenClosed = NO;
    NSTextField *instructions = [NSTextField wrappingLabelWithString:@"Smooth panel navigation — experimental\n\nKeep 3DconnexionHelper running. Floating Node Editor: full graph X/Z pan and Y zoom; inspector scrolls. Timeline: experimental X/Z touch pan and Y pinch zoom. Objects: X/Z scroll. Floating Attributes: Z scrolls vertically. Background C4D plugin tracks live panel geometry. Controls are in the SM Trial menu."];
    instructions.frame = NSMakeRect(24, 108, 532, 128);
    [self.window.contentView addSubview:instructions];
    self.statusLabel = [NSTextField wrappingLabelWithString:@"Paused — no input takeover"];
    self.statusLabel.frame = NSMakeRect(24, 68, 532, 36);
    [self.window.contentView addSubview:self.statusLabel];
    NSButton *start = [NSButton buttonWithTitle:@"Start / Pause" target:self action:@selector(toggle:)];
    start.frame = NSMakeRect(24, 20, 140, 32);
    [self.window.contentView addSubview:start];
    NSButton *access = [NSButton buttonWithTitle:@"Accessibility permission…" target:self action:@selector(permissions:)];
    access.frame = NSMakeRect(180, 20, 220, 32);
    [self.window.contentView addSubview:access];
    NSButton *quitButton = [NSButton buttonWithTitle:@"Quit" target:self action:@selector(quit:)];
    quitButton.frame = NSMakeRect(440, 20, 100, 32);
    [self.window.contentView addSubview:quitButton];
    [self.window center];
    [self.window makeKeyAndOrderFront:nil];
    self.lastTick = NSProcessInfo.processInfo.systemUptime;
    self.timer = [NSTimer timerWithTimeInterval:1.0/120.0 target:self selector:@selector(tick:) userInfo:nil repeats:YES];
    self.timer.tolerance = 0.0005;
    [NSRunLoop.mainRunLoop addTimer:self.timer forMode:NSRunLoopCommonModes];
    fprintf(stdout, "SpaceMouse C4D trial ready; paused. Use SM Trial in the menu bar.\n");
    fflush(stdout);
}
- (void)permissions:(id)sender {
    AXIsProcessTrustedWithOptions((__bridge CFDictionaryRef)@{(__bridge NSString *)kAXTrustedCheckOptionPrompt: @YES});
    self.statusItem.title = AXIsProcessTrusted() ? @"Accessibility granted" : @"Grant Accessibility, then start trial";
}
- (void)toggle:(id)sender {
    if (self.starting) return;
    if (!self.enabled) {
        if (!AXIsProcessTrusted() || !CGPreflightPostEventAccess()) {
            [self permissions:nil];
            self.statusItem.title = @"Accessibility required before starting";
            return;
        }
        self.starting = YES;
        self.statusItem.title = @"Connecting to driver…";
        // The driver handshake must not block the application's main run loop.
        SDKAsync(^{
            int16_t error = SetConnexionHandlers(receive, NULL, NULL, true);
            uint8_t name[] = "\022SpaceMouseC4DTrial";
            uint16_t registered = error ? 0 : RegisterConnexionClient(kConnexionClientManual,
                name, kConnexionClientModeTakeOver, kConnexionMaskAxis);
            if (registered) SetConnexionClientButtonMask(registered, 0);
            else if (!error) CleanupConnexionHandlers();
            dispatch_async(dispatch_get_main_queue(), ^{
                self.starting = NO;
                if (self.terminating) {
                    clientID = registered;
                    [self finishTermination];
                    return;
                }
                if (!registered) {
                    self.statusItem.title = [NSString stringWithFormat:@"Driver registration failed (handlers=%d)", error];
                    return;
                }
                clientID = registered;
                self.enabled = YES;
                self.lastContext = 0;
                self.toggleItem.title = @"Pause trial and restore navigation";
            });
        });
    } else {
        [self stop];
    }
}
- (void)toggleZoom:(id)sender {
    [self endGesture];
    self.zoomEnabled = !self.zoomEnabled;
    self.zoomItem.state = self.zoomEnabled ? NSControlStateValueOn : NSControlStateValueOff;
    [NSUserDefaults.standardUserDefaults setBool:self.zoomEnabled forKey:@"zoomEnabled"];
}
- (void)toggleInvertX:(id)sender {
    [self endGesture];
    self.invertX = !self.invertX;
    self.invertXItem.state = self.invertX ? NSControlStateValueOn : NSControlStateValueOff;
    [NSUserDefaults.standardUserDefaults setBool:self.invertX forKey:@"invertHorizontal"];
}
- (void)selectZoomGain:(NSMenuItem *)sender {
    [self endGesture];
    self.zoomGain = [sender.representedObject doubleValue];
    [NSUserDefaults.standardUserDefaults setDouble:self.zoomGain forKey:@"zoomGain"];
    self.zoomGainItem.title = [NSString stringWithFormat:@"Zoom sensitivity: %gx", self.zoomGain];
    for (NSMenuItem *choice in self.zoomGainItem.submenu.itemArray)
        choice.state = choice == sender ? NSControlStateValueOn : NSControlStateValueOff;
}
- (void)toggleInvertY:(id)sender {
    [self endGesture];
    self.invertY = !self.invertY;
    self.invertYItem.state = self.invertY ? NSControlStateValueOn : NSControlStateValueOff;
    [NSUserDefaults.standardUserDefaults setBool:self.invertY forKey:@"invertVertical"];
}
- (void)postX:(double)x y:(double)y phase:(int64_t)phase zoom:(BOOL)zoom {
    if (self.targetPID <= 0 || !self.targetWindowID) return;
    CGEventRef event = makeScroll(x, y, phase, zoom);
    if (self.timelineContext) {
        static int output = -1;
        if (output < 0) {
            output = socket(AF_UNIX, SOCK_DGRAM, 0);
            if (output >= 0) fcntl(output, F_SETFL, O_NONBLOCK);
        }
        CGPoint point = CGEventGetLocation(event);
        CGPoint local = CGPointMake(point.x-self.targetWindowFrame.origin.x,
                                    CGRectGetMaxY(self.targetWindowFrame)-point.y);
        NSDictionary *packet = @{@"pid":@(self.targetPID), @"window":@(self.targetWindowID),
            @"time":@(NSDate.date.timeIntervalSince1970), @"screen":@[@(point.x),@(point.y)],
            @"local":@[@(local.x),@(local.y)], @"dx":@(x), @"dy":@(y), @"phase":@(phase), @"zoom":@(zoom)};
        NSData *data = [NSJSONSerialization dataWithJSONObject:packet options:0 error:nil];
        struct sockaddr_un address = {0}; address.sun_family=AF_UNIX;
        strlcpy(address.sun_path, "/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-input.sock", sizeof address.sun_path);
        if (output < 0 || sendto(output, data.bytes, data.length, 0, (struct sockaddr *)&address, sizeof address) < 0)
            self.statusItem.title = @"Timeline gesture transport unavailable";
        CFRelease(event);
        return;
    }
    if (self.dockedPanel && !self.verticalOnly) {
        // Plain list scrolling follows the real pointer through C4D's normal
        // window-server route. No synthetic hover or centered coordinates.
        CGEventPost(kCGHIDEventTap, event);
        CFRelease(event);
        return;
    }
    anchorZoom(event, zoom || self.verticalOnly, self.zoomCenter);
    addressWindow(event, self.targetPID, self.targetWindowID);
    // AppKit needs both a window address and its own hover tracking updated.
    // This virtual move goes ONLY to C4D's queue, not to the system pointer.
    CGPoint point = CGEventGetLocation(event);
    CGPoint local = CGPointMake(point.x - self.targetWindowFrame.origin.x,
                               CGRectGetMaxY(self.targetWindowFrame) - point.y);
    CGEventRef tracking = makeTracking(point, local, self.targetWindowID, self.targetPID);
    setWindowLocation(tracking, local);
    // The scroll's window number is a Quartz SPI field, separate from the
    // public under-pointer fields which are ignored on raw scroll events here.
    CGEventSetIntegerValueField(event, (CGEventField)51, self.targetWindowID);
    setWindowLocation(event, local);
    CGEventPostToPid(self.targetPID, tracking);
    CFRelease(tracking);
    // Use the application's event stream for BOTH pan and zoom, preserving
    // their order and avoiding the HID stream's global cursor relocation.
    CGEventPostToPid(self.targetPID, event);
    CFRelease(event);
}
- (void)endGesture {
    if (self.gesture) [self postX:0 y:0 phase:4 zoom:NO];
    if (self.zoomGesture) [self postX:0 y:0 phase:4 zoom:YES];
    self.gesture = NO;
    self.zoomGesture = NO;
    self.remainderX = self.remainderY = 0;
    self.zoomRemainder = 0;
}
- (void)emitX:(double)dx y:(double)dy zoom:(BOOL)zoom {
    BOOL running = zoom ? self.zoomGesture : self.gesture;
    if (fabs(dx) + fabs(dy) < 0.00001) {
        if (running) [self postX:0 y:0 phase:4 zoom:zoom];
        if (zoom) {
            self.zoomGesture = NO;
            self.zoomRemainder = 0;
        } else {
            self.gesture = NO;
            self.remainderX = self.remainderY = 0;
        }
        return;
    }
    double px, py;
    if (zoom) {
        self.zoomRemainder += dy;
        px = 0;
        py = trunc(self.zoomRemainder);
        self.zoomRemainder -= py;
    } else {
        self.remainderX += dx;
        self.remainderY += dy;
        px = trunc(self.remainderX);
        py = trunc(self.remainderY);
        self.remainderX -= px;
        self.remainderY -= py;
    }
    if (px == 0 && py == 0) return;
    if (!running) [self postX:0 y:0 phase:128 zoom:zoom];
    [self postX:px y:py phase:running ? 2 : 1 zoom:zoom];
    if (zoom) self.zoomGesture = YES;
    else self.gesture = YES;
}
- (void)releaseDevice {
    [self endGesture];
    if (self.claimed && clientID) {
        int32_t result = 0;
        ConnexionClientControl(clientID, kConnexionCtlDeactivateClient, 0, &result);
    }
    self.claimed = NO;
    memset(axes, 0, sizeof axes);
}
- (void)stop {
    [self releaseDevice];
    if (clientID) {
        uint16_t oldID = clientID;
        clientID = 0;
        SDKAsync(^{
            UnregisterConnexionClient(oldID);
            CleanupConnexionHandlers();
        });
    }
    self.enabled = NO;
    self.toggleItem.title = @"Start smooth navigation trial";
    self.statusItem.title = @"Paused — normal navigation restored";
}
- (void)refreshContext {
    self.graphRect = CGRectZero;
    self.contextReason = @"Cinema 4D is not foreground";
    NSRunningApplication *front = NSWorkspace.sharedWorkspace.frontmostApplication;
    if (![front.bundleIdentifier isEqualToString:@"net.maxon.cinema4d"]) return;
    AXUIElementRef app = AXUIElementCreateApplication(front.processIdentifier);
    id window = attribute(app, kAXFocusedWindowAttribute);
    CFRelease(app);
    if (!window) { self.contextReason = [NSString stringWithFormat:@"Cannot read focused C4D window (Accessibility=%d)", AXIsProcessTrusted()]; return; }
    AXUIElementRef win = (__bridge AXUIElementRef)window;
    NSString *title = attribute(win, kAXTitleAttribute);
    BOOL mainWindow = [title hasSuffix:@" - Main"];
    BOOL node = [title isEqualToString:@"Node Editor"];
    BOOL animation = [title isEqualToString:@"Timeline"] || [title hasPrefix:@"Timeline ("];
    BOOL timelineWindow = animation;
    BOOL objects = [title isEqualToString:@"Objects"] || [title hasPrefix:@"Objects ("];
    BOOL attributes = [title isEqualToString:@"Attributes"] || [title hasPrefix:@"Attributes ("];
    if (!node && !objects && !attributes && !mainWindow && !animation) { self.contextReason = [NSString stringWithFormat:@"Unsupported window: %@", title]; return; }
    id position = attribute(win, kAXPositionAttribute);
    id size = attribute(win, kAXSizeAttribute);
    if (!position || !size) { self.contextReason = @"Cannot read Node Editor bounds"; return; }
    CGPoint p; CGSize s;
    if (!AXValueGetValue((__bridge AXValueRef)position, kAXValueCGPointType, &p) ||
        !AXValueGetValue((__bridge AXValueRef)size, kAXValueCGSizeType, &s)) return;
    CGRect dockedRect = CGRectZero;
    if (mainWindow) {
        NSData *data = [NSData dataWithContentsOfFile:@"/Users/leah/Documents/Projects/SpaceMouse/.build/live-layout.json"];
        NSDictionary *layout = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        double age = NSDate.date.timeIntervalSince1970 - [layout[@"timestamp"] doubleValue];
        if (![layout isKindOfClass:NSDictionary.class] || [layout[@"pid"] intValue] != front.processIdentifier || age < 0 || age > 0.3) {
            self.contextReason = @"Waiting for live C4D layout bridge";
            return;
        }
        NSMutableArray *rects = [NSMutableArray array];
        for (NSDictionary *frame in layout[@"viewports"]) {
            double l = [frame[@"cl"] doubleValue], t = [frame[@"ct"] doubleValue];
            double r = [frame[@"cr"] doubleValue], b = [frame[@"cb"] doubleValue];
            if (!isfinite(l) || !isfinite(t) || !isfinite(r) || !isfinite(b) || r-l < 10 || b-t < 10) continue;
            // Include the viewport's border and local header in native 3D mode.
            CGRect viewport = CGRectMake(l-8, t-30, r-l+17, b-t+39);
            [rects addObject:[NSValue valueWithRect:NSRectFromCGRect(viewport)]];
        }
        if (!rects.count) { self.contextReason = @"Live bridge has no visible viewport bounds"; return; }
        self.liveViewports = rects;
        self.layoutTimestamp = [layout[@"timestamp"] doubleValue];
        dockedRect = CGRectMake(p.x+8, p.y+90, s.width-16, s.height-125);
    }

    // Deliberately limited proof of concept: the LEFT HALF of the standard
    // floating Node Editor, with toolbars and footer excluded. This is not
    // general panel discovery. The right-side inspector is never targeted.
    if (s.width < (node ? 400 : 180) || s.height < (node ? 300 : 160)) return;
    CGWindowID windowID = focusedWindowID(win, front.processIdentifier, (CGRect){p, s});
    if (!windowID) { self.contextReason = [NSString stringWithFormat:@"Cannot resolve focused window ID for %.0f,%.0f %.0fx%.0f", p.x,p.y,s.width,s.height]; return; }
    CGRect graphViewport = CGRectZero;
    CGRect timelineViewport = CGRectZero;
    NSData *timelineData = [NSData dataWithContentsOfFile:@"/Users/leah/Documents/Projects/SpaceMouse/.build/live-layout.json"];
    NSDictionary *timelineLayout = timelineData ? [NSJSONSerialization JSONObjectWithData:timelineData options:0 error:nil] : nil;
    double timelineAge = NSDate.date.timeIntervalSince1970 - [timelineLayout[@"timestamp"] doubleValue];
    self.liveTimelines = @[];
    if ([timelineLayout[@"pid"] intValue] == front.processIdentifier && timelineAge >= 0 && timelineAge < 0.3) {
        self.liveTimelines = timelineLayout[@"timelines"] ?: @[];
        CGEventRef cursor = CGEventCreate(NULL);
        CGPoint pointer = CGEventGetLocation(cursor);
        CFRelease(cursor);
        for (NSDictionary *panel in self.liveTimelines) {
            if ([panel[@"window"] unsignedIntValue] != windowID) continue;
            CGRect bounds = CGRectMake([panel[@"x"] doubleValue], [panel[@"y"] doubleValue],
                                       [panel[@"width"] doubleValue], [panel[@"height"] doubleValue]);
            if (CGRectContainsPoint(bounds, pointer)) { timelineViewport = bounds; break; }
        }
    }
    // A Timeline manager may live inside the main window or a floating host.
    // Its live SDK bounds determine routing, independently of the host title.
    animation = !CGRectIsEmpty(timelineViewport);
    if (timelineWindow && !animation) { self.contextReason = @"Waiting for live Timeline panel bounds"; return; }
    BOOL nodeInspector = NO;
    if (node) {
        NSData *data = [NSData dataWithContentsOfFile:@"/Users/leah/Documents/Projects/SpaceMouse/.build/live-layout.json"];
        NSDictionary *layout = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        double age = NSDate.date.timeIntervalSince1970 - [layout[@"timestamp"] doubleValue];
        if ([layout[@"pid"] intValue] != front.processIdentifier || age < 0 || age > 0.3) {
            self.contextReason = @"Waiting for live Node Editor geometry"; return;
        }
        for (NSDictionary *graph in layout[@"nodeGraphs"]) {
            if ([graph[@"window"] unsignedIntValue] != windowID) continue;
            graphViewport = CGRectMake([graph[@"x"] doubleValue], [graph[@"y"] doubleValue],
                                       [graph[@"width"] doubleValue], [graph[@"height"] doubleValue]);
            break;
        }
        if (CGRectIsEmpty(graphViewport) || !CGRectContainsRect((CGRect){p,s}, graphViewport)) {
            self.contextReason = @"No live graph view for focused Node Editor"; return;
        }
        self.layoutTimestamp = [layout[@"timestamp"] doubleValue];
        CGEventRef location = CGEventCreate(NULL);
        nodeInspector = !CGRectContainsPoint(graphViewport, CGEventGetLocation(location));
        CFRelease(location);
    }
    BOOL listPanel = (!node && !animation) || nodeInspector;
    BOOL normalRoute = mainWindow || nodeInspector || animation;
    if (self.listPanel != listPanel || self.dockedPanel != normalRoute || self.targetWindowID != windowID)
        [self endGesture];
    self.timelineContext = animation;
    self.listPanel = listPanel;
    self.dockedPanel = normalRoute;
    self.verticalOnly = attributes;
    self.mainWindowContext = mainWindow;
    self.nodeWindowContext = node;
    self.nodeGraphRect = graphViewport;
    self.contextReason = @"Pointer outside panel content or mouse button held";
    self.targetWindowID = windowID;
    self.targetWindowFrame = (CGRect){p,s};
    self.graphRect = CGRectMake(p.x+8, p.y+(attributes ? 106 : 55), s.width-16,
                               s.height-(attributes ? 114 : 63));
    if (node) {
        self.graphRect = nodeInspector ? CGRectMake(p.x+2, CGRectGetMinY(graphViewport), s.width-4,
                                                     CGRectGetHeight(graphViewport)) : graphViewport;
        self.zoomCenter = CGPointMake(CGRectGetMidX(graphViewport), CGRectGetMidY(graphViewport));
    }
    if (animation) self.graphRect = CGRectMake(p.x+4, p.y+100, s.width-8, s.height-115);
    if (mainWindow) self.graphRect = dockedRect;
    if (animation) {
        self.graphRect = CGRectInset(timelineViewport, 0, 0);
        self.layoutTimestamp = [timelineLayout[@"timestamp"] doubleValue];
    }
    if (attributes) self.zoomCenter = CGPointMake(CGRectGetMinX(self.graphRect), CGRectGetMidY(self.graphRect));
    self.targetPID = front.processIdentifier;
}
- (void)tick:(NSTimer *)timer {
    double now = NSProcessInfo.processInfo.systemUptime;
    static double lastStatusTime;
    static NSString *lastStatus;
    // Diagnostic/UI work must not run at device-report frequency.
    if (now - lastStatusTime >= 1.0) {
        lastStatusTime = now;
        self.statusLabel.stringValue = self.statusItem.title;
      if (![lastStatus isEqualToString:self.statusItem.title]) {
        lastStatus = [self.statusItem.title copy];
        NSString *line = [NSString stringWithFormat:@"%@ %@\n", NSDate.date, lastStatus];
        NSFileHandle *log = [NSFileHandle fileHandleForWritingAtPath:@"/Users/leah/Documents/Projects/SpaceMouse/.build/trial-status.log"];
        if (!log) [line writeToFile:@"/Users/leah/Documents/Projects/SpaceMouse/.build/trial-status.log" atomically:YES encoding:NSUTF8StringEncoding error:nil];
        else { [log seekToEndOfFile]; [log writeData:[line dataUsingEncoding:NSUTF8StringEncoding]]; [log closeFile]; }
    }
    }
    double dt = fmin(fmax(now - self.lastTick, 0), 0.025);
    self.lastTick = now;
    if (!self.enabled) return;
    if (now - self.lastContext > 0.08) {
        [self refreshContext];
        self.lastContext = now;
    }
    // Frontmost identity is rechecked every tick; never post into another app
    // during the context cache interval. Physical mouse buttons suspend output.
    NSRunningApplication *front = NSWorkspace.sharedWorkspace.frontmostApplication;
    CGEventRef locationEvent = CGEventCreate(NULL);
    CGPoint pointer = CGEventGetLocation(locationEvent);
    CFRelease(locationEvent);
    if (self.nodeWindowContext && self.listPanel == CGRectContainsPoint(self.nodeGraphRect, pointer))
        [self refreshContext];
    if (self.mainWindowContext) {
        BOOL overTimeline = NO;
        for (NSDictionary *panel in self.liveTimelines) {
            if ([panel[@"window"] unsignedIntValue] != self.targetWindowID) continue;
            CGRect bounds = CGRectMake([panel[@"x"] doubleValue], [panel[@"y"] doubleValue],
                                       [panel[@"width"] doubleValue], [panel[@"height"] doubleValue]);
            if (CGRectContainsPoint(bounds, pointer)) { overTimeline = YES; break; }
        }
        if (overTimeline != self.timelineContext) [self refreshContext];
    }
    BOOL inViewport = NO;
    if (self.mainWindowContext) {
        for (NSValue *value in self.liveViewports)
            if (CGRectContainsPoint(NSRectToCGRect(value.rectValue), pointer)) { inViewport = YES; break; }
        if (NSDate.date.timeIntervalSince1970 - self.layoutTimestamp > 0.3) inViewport = YES;
    }
    if (self.nodeWindowContext && NSDate.date.timeIntervalSince1970 - self.layoutTimestamp > 0.3) inViewport = YES;
    BOOL eligible = !inViewport && front.processIdentifier == self.targetPID &&
        CGRectContainsPoint(self.graphRect, pointer) &&
        !CGEventSourceButtonState(kCGEventSourceStateCombinedSessionState, kCGMouseButtonLeft) &&
        !CGEventSourceButtonState(kCGEventSourceStateCombinedSessionState, kCGMouseButtonRight) &&
        !CGEventSourceButtonState(kCGEventSourceStateCombinedSessionState, kCGMouseButtonCenter);
    if (!eligible) {
        if (self.claimed) [self releaseDevice];
        self.statusItem.title = [NSString stringWithFormat:@"%@ (reports=%lu)", self.contextReason, (unsigned long)inputCount];
        return;
    }
    if (!self.claimed) {
        int32_t result = 0;
        int16_t error = ConnexionClientControl(clientID, kConnexionCtlActivateClient, 0, &result);
        if (error) {
            self.statusItem.title = [NSString stringWithFormat:@"Driver activation failed (%d)", error];
            return;
        }
        self.claimed = YES;
        lastInput = 0;
        memset(axes, 0, sizeof axes);
    }
    self.statusItem.title = [NSString stringWithFormat:@"Smooth navigation: %lu reports", (unsigned long)inputCount];
    if (now - lastInput > 0.25) {
        [self endGesture];
        return;
    }
    double vx = self.verticalOnly ? 0 : response(axes[0]), vy = response(axes[2]);
    double vz = self.zoomEnabled && !self.listPanel ? response(axes[1]) : 0;
    double dx = vx * 1000 * dt * (self.invertX ? -1 : 1);
    double dy = -vy * 1000 * dt * (self.invertY ? -1 : 1);
    double dz = vz * 350 * self.zoomGain * dt;
    // Independent accumulators and phases: neither movement suppresses the
    // other. C4D sees ordinary pixel-pan and Control+pixel-zoom each tick.
    [self emitX:dx y:dy zoom:NO];
    [self emitX:0 y:dz zoom:YES];
    if ((self.gesture || self.zoomGesture) && now - self.lastLog > 0.2) {
        fprintf(stdout, "reports=%lu axis=(%.0f,%.0f,%.0f) delta=(%.3f,%.3f,%.3f) pan=%d zoom=%d\n",
                (unsigned long)inputCount, axes[0], axes[1], axes[2], dx, dy, dz, self.gesture, self.zoomGesture);
        fflush(stdout);
        self.lastLog = now;
    }
}
- (void)quit:(id)sender { [NSApp terminate:nil]; }
- (void)finishTermination {
    [self stop];
    SDKAsync(^{
        dispatch_async(dispatch_get_main_queue(), ^{ [NSApp replyToApplicationShouldTerminate:YES]; });
    });
}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    self.terminating = YES;
    if (!self.starting) [self finishTermination];
    return NSTerminateLater;
}
@end

// Capture the actual output events without posting them for lifecycle checks.
@interface EventProbe : Probe
@property NSMutableArray<NSEvent *> *events;
@end
@implementation EventProbe
- (void)postX:(double)x y:(double)y phase:(int64_t)phase zoom:(BOOL)zoom {
    CGEventRef event = makeScroll(x, y, phase, zoom);
    anchorZoom(event, zoom, self.zoomCenter);
    [self.events addObject:[NSEvent eventWithCGEvent:event]];
    CFRelease(event);
}
@end

static int selfTest(void) {
    @autoreleasepool {
        if (response(0) != 0 || response(10) != 0 || fabs(response(350) - 1) > 1e-9 ||
            fabs(response(-175) + response(175)) > 1e-9) return 1;
        CGEventRef event = makeScroll(1, -2, 2, NO);
        NSEvent *ns = [NSEvent eventWithCGEvent:event];
        printf("continuous=%lld precise=%d point=(%lld,%lld) AppKit=(%.6f,%.6f) phase=%lu\n",
               CGEventGetIntegerValueField(event, kCGScrollWheelEventIsContinuous), ns.hasPreciseScrollingDeltas,
               CGEventGetIntegerValueField(event, kCGScrollWheelEventPointDeltaAxis2),
               CGEventGetIntegerValueField(event, kCGScrollWheelEventPointDeltaAxis1),
               ns.scrollingDeltaX, ns.scrollingDeltaY, (unsigned long)ns.phase);
        BOOL passed = ns.hasPreciseScrollingDeltas && ns.phase == NSEventPhaseChanged &&
                      fabs(ns.scrollingDeltaX - 1) < 0.001 && fabs(ns.scrollingDeltaY + 2) < 0.001;
        CFRelease(event);
        EventProbe *probe = [EventProbe new];
        probe.zoomCenter = CGPointMake(400, 350);
        probe.events = [NSMutableArray new];
        [probe emitX:2 y:1 zoom:NO];
        [probe emitX:0 y:3 zoom:YES];
        passed = passed && probe.gesture && probe.zoomGesture && probe.events.count == 4 &&
            probe.events[1].scrollingDeltaX == 2 &&
            !(probe.events[1].modifierFlags & NSEventModifierFlagControl) &&
            probe.events[3].scrollingDeltaY == 3 &&
            (probe.events[3].modifierFlags & NSEventModifierFlagControl);
        passed = passed && CGPointEqualToPoint(CGEventGetLocation(probe.events[3].CGEvent), probe.zoomCenter);
        [probe emitX:1 y:0 zoom:NO];
        [probe emitX:0 y:0 zoom:YES];
        passed = passed && probe.gesture && !probe.zoomGesture &&
            !(probe.events[4].modifierFlags & NSEventModifierFlagControl) &&
            probe.events.lastObject.phase == NSEventPhaseEnded;
        [probe endGesture];
        passed = passed && !probe.gesture && !probe.zoomGesture;
        [probe.events removeAllObjects];
        for (int i = 0; i < 4; ++i) [probe emitX:0.25 y:0 zoom:NO];
        passed = passed && probe.events.count == 2 && probe.events.lastObject.scrollingDeltaX == 1;
        CGEventRef anchorTest = makeScroll(0, 1, 2, YES);
        addressWindow(anchorTest, 1234, 5678);
        printf("address fields: pid=%lld window=%lld handler=%lld\n",
            CGEventGetIntegerValueField(anchorTest, kCGEventTargetUnixProcessID),
            CGEventGetIntegerValueField(anchorTest, kCGMouseEventWindowUnderMousePointer),
            CGEventGetIntegerValueField(anchorTest, kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent));
        passed = passed && CGEventGetIntegerValueField(anchorTest, kCGEventTargetUnixProcessID) == 1234;
        CGEventRef trackingTest = makeTracking(CGPointMake(400, 350), CGPointMake(100, 200), 5678, 1234);
        NSEvent *trackingNS = [NSEvent eventWithCGEvent:trackingTest];
        printf("AppKit tracking window=%ld; window-location SPI=%s\n", (long)trackingNS.windowNumber,
               dlsym(RTLD_DEFAULT, "CGEventSetWindowLocation") ? "available" : "unavailable");
        passed = passed && trackingNS.windowNumber == 5678;
        CFRelease(trackingTest);
        CGEventSetLocation(anchorTest, CGPointMake(10, 20));
        anchorZoom(anchorTest, YES, CGPointMake(400, 350));
        passed = passed && CGPointEqualToPoint(CGEventGetLocation(anchorTest), CGPointMake(400, 350));
        CGEventSetLocation(anchorTest, CGPointMake(90, 80));
        anchorZoom(anchorTest, YES, CGPointMake(400, 350));
        passed = passed && CGPointEqualToPoint(CGEventGetLocation(anchorTest), CGPointMake(400, 350));
        CGEventSetLocation(anchorTest, CGPointMake(10, 20));
        anchorZoom(anchorTest, NO, CGPointMake(400, 350));
        passed = passed && CGPointEqualToPoint(CGEventGetLocation(anchorTest), CGPointMake(10, 20));
        CFRelease(anchorTest);
        printf("response symmetry, dead zone, pixel precision, gesture phase: %s\n", passed ? "PASS" : "FAIL");
        printf("concurrent pan/zoom, independent stop, subpixel accumulation: %s\n", passed ? "PASS" : "FAIL");
        printf("graph-centered zoom independent of pointer, pan location preserved: %s\n", passed ? "PASS" : "FAIL");
        return passed ? 0 : 1;
    }
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc > 1 && strcmp(argv[1], "--self-test") == 0) return selfTest();
        if (argc > 1 && strcmp(argv[1], "--driver-test") == 0) {
            [NSApplication sharedApplication];
            __block BOOL success = YES;
            SDKAsync(^{
              for (int cycle = 0; cycle < 3; ++cycle) {
                int16_t error = SetConnexionHandlers(receive, NULL, NULL, true);
                uint8_t name[] = "\022SpaceMouseC4DTrial";
                if (!error) clientID = RegisterConnexionClient(kConnexionClientManual, name,
                    kConnexionClientModeTakeOver, kConnexionMaskAxis);
                printf("SDK handlers=%d manual client=%u (not activated; no input posted)\n", error, clientID);
                success = success && !error && clientID;
                if (clientID) UnregisterConnexionClient(clientID);
                if (!error) CleanupConnexionHandlers();
                clientID = 0;
              }
                dispatch_async(dispatch_get_main_queue(), ^{ CFRunLoopStop(CFRunLoopGetMain()); });
            });
            CFRunLoopRun();
            return success ? 0 : 1;
        }
        NSApplication *app = NSApplication.sharedApplication;
        Probe *probe = [Probe new];
        app.delegate = probe;
        [app run];
    }
    return 0;
}
