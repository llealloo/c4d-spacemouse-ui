#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <ConnexionClientAPI.h>
#import <objc/runtime.h>
#import <CommonCrypto/CommonDigest.h>
#include <mach-o/dyld.h>
#include <pthread.h>
#include <math.h>
#include <string.h>
#include <dlfcn.h>

typedef struct { int ready,error,client,claimed; uint64_t reports; double axes[6],lastInput; } SMInput;
typedef struct { int64_t window; int active,buttons; double x,y,wx,wy,width,height; char title[512]; } SMContext;
static SMInput input;
static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static BOOL started,suppressed;
static id hookedAPI;
static void **hookedSlot;
typedef void (*Handler3)(unsigned int,unsigned int,void *);
typedef void (*Handler4)(unsigned int,unsigned int,void *,void *);
static Handler3 original3;
static Handler4 original4;
static uintptr_t sdkBase;
static double lastAttach;

static BOOL capture(unsigned int message,void *argument,ConnexionDeviceState *zero,BOOL *stopVendor) {
    *stopVendor=NO;
    if(message!=kConnexionMsgDeviceState || !argument)return NO;
    const ConnexionDeviceState *state=argument;
    pthread_mutex_lock(&mutex);
    BOOL matching=started && state->client==input.client && state->command==kConnexionCmdHandleAxis;
    BOOL consume=matching && input.claimed;
    if(matching) {
        for(int i=0;i<6;++i)input.axes[i]=state->axis[i];
        input.lastInput=NSProcessInfo.processInfo.systemUptime;++input.reports;
        if(consume && !suppressed) {
            *zero=*state;memset(zero->axis,0,sizeof zero->axis);*stopVendor=YES;
        }
        suppressed=consume;
    }
    pthread_mutex_unlock(&mutex);
    return consume;
}
static void forward3(unsigned int device,unsigned int message,void *argument) {
    Handler3 handler=__atomic_load_n(&original3,__ATOMIC_ACQUIRE);
    if(!handler)return;
    ConnexionDeviceState zero;BOOL stop;
    if(!capture(message,argument,&zero,&stop))handler(device,message,argument);
    else if(stop)handler(device,message,&zero);
}
static void forward4(unsigned int device,unsigned int message,void *argument,void *context) {
    Handler4 handler=__atomic_load_n(&original4,__ATOMIC_ACQUIRE);
    if(!handler)return;
    ConnexionDeviceState zero;BOOL stop;
    if(!capture(message,argument,&zero,&stop))handler(device,message,argument,context);
    else if(stop)handler(device,message,&zero,context);
}
static BOOL inspectSDK(void) {
    Dl_info location;
    if(!dladdr((const void*)&ConnexionClientControl,&location) || !location.dli_fname)return NO;
    NSData *data=[NSData dataWithContentsOfFile:@(location.dli_fname)];
    if(!data)return NO;
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
    NSMutableString *hash=[NSMutableString new];
    for(int i=0;i<CC_SHA256_DIGEST_LENGTH;++i)[hash appendFormat:@"%02x",digest[i]];
    if(![hash isEqualToString:@"377cb3a9efda8a9496e202dce33055f7d1908d51e9e069d07419b6c8d442ae07"])return NO;
    Class cls=NSClassFromString(@"ConnexionClientAPI");
    Ivar standard=class_getInstanceVariable(cls,"deviceMessageHandler");
    Ivar extended=class_getInstanceVariable(cls,"deviceMessageHandler2");
    if(!standard || !extended || ivar_getOffset(standard)!=32 || ivar_getOffset(extended)!=56 || class_getInstanceSize(cls)!=5096)return NO;
    for(uint32_t i=0;i<_dyld_image_count();++i) {
        const char *name=_dyld_get_image_name(i);
        if(name && [[@(name) lastPathComponent] isEqualToString:@"3DconnexionClient"]) {sdkBase=(uintptr_t)_dyld_get_image_header(i);return YES;}
    }
    return NO;
}
static void detach(void) {
    if(hookedSlot) {
        void *current=__atomic_load_n(hookedSlot,__ATOMIC_ACQUIRE);
        if(current==(void*)&forward3) {
            void *expected=current;__atomic_compare_exchange_n(hookedSlot,&expected,(void*)original3,NO,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
        } else if(current==(void*)&forward4) {
            void *expected=current;__atomic_compare_exchange_n(hookedSlot,&expected,(void*)original4,NO,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
        }
    }
    hookedSlot=NULL;hookedAPI=nil;
    pthread_mutex_lock(&mutex);input.ready=0;input.claimed=0;suppressed=NO;pthread_mutex_unlock(&mutex);
}
static void attach(void) {
    if(!started || !sdkBase || !NSThread.isMainThread)return;
    double now=NSProcessInfo.processInfo.systemUptime;
    if(now-lastAttach<.25)return;lastAttach=now;
    // Read the exact inspected SDK's registry under the same lock it uses.
    // This never registers/deactivates clients or changes a driver setting.
    void *registryPointer=*(void**)(sdkBase+0x1c0c0);
    NSDictionary *registry=(__bridge NSDictionary*)registryPointer;
    if(!registry)return;
    NSDictionary *clients;
    @synchronized(registry){clients=[registry copy];}
    id vendor=nil;int clientID=0;
    for(NSNumber *key in clients) {
        id api=clients[key][@"object"];
        if(![api isKindOfClass:NSClassFromString(@"ConnexionClientAPI")])continue;
        id info=[api valueForKey:@"applicationInfo"];
        if([[info valueForKey:@"clientName"] isEqualToString:@"Cinema4d"] &&
           [[info valueForKey:@"bundleid"] isEqualToString:@"net.maxon.cinema4d"]) {vendor=api;clientID=key.intValue;break;}
    }
    if(hookedAPI==vendor && vendor) {
        pthread_mutex_lock(&mutex);input.client=clientID;pthread_mutex_unlock(&mutex);return;
    }
    if(hookedAPI)detach();
    if(!vendor)return;
    void *standard=__atomic_load_n((void**)((__bridge void*)vendor+32),__ATOMIC_ACQUIRE);
    void *extended=__atomic_load_n((void**)((__bridge void*)vendor+56),__ATOMIC_ACQUIRE);
    void *callback=standard?:extended;
    Dl_info owner;
    if(!callback || !dladdr(callback,&owner) || !strstr(owner.dli_fname?:"","3DconnexionNavlib")) {
        pthread_mutex_lock(&mutex);input.error=-3;pthread_mutex_unlock(&mutex);return;
    }
    void **slot=(void**)((__bridge void*)vendor+(standard?32:56));
    if(standard)__atomic_store_n(&original3,(Handler3)standard,__ATOMIC_RELEASE);
    else __atomic_store_n(&original4,(Handler4)extended,__ATOMIC_RELEASE);
    pthread_mutex_lock(&mutex);input.client=clientID;input.claimed=0;suppressed=NO;pthread_mutex_unlock(&mutex);
    void *expected=callback;
    if(!__atomic_compare_exchange_n(slot,&expected,standard?(void*)&forward3:(void*)&forward4,NO,__ATOMIC_RELEASE,__ATOMIC_RELAXED))return;
    hookedAPI=vendor;hookedSlot=slot;
    pthread_mutex_lock(&mutex);input.ready=1;input.error=0;pthread_mutex_unlock(&mutex);
}
__attribute__((visibility("default"))) void SMUIStart(void) {
    if(started)return;
    BOOL valid=inspectSDK();
    pthread_mutex_lock(&mutex);memset(&input,0,sizeof input);started=valid;input.error=valid?0:-2;pthread_mutex_unlock(&mutex);
    lastAttach=0;if(valid)attach();
}
__attribute__((visibility("default"))) void SMUIRead(SMInput *out) {
    attach();pthread_mutex_lock(&mutex);*out=input;pthread_mutex_unlock(&mutex);
}
__attribute__((visibility("default"))) void SMUIClaim(int claim) {
    pthread_mutex_lock(&mutex);
    BOOL eligible=claim && input.ready && started;
    if(input.claimed!=eligible) {
        input.claimed=eligible;memset(input.axes,0,sizeof input.axes);input.lastInput=0;
    }
    pthread_mutex_unlock(&mutex);
}
__attribute__((visibility("default"))) void SMUIStop(void) {
    pthread_mutex_lock(&mutex);started=NO;input.claimed=0;pthread_mutex_unlock(&mutex);
    detach();
}
__attribute__((visibility("default"))) void SMUIContext(SMContext *out) {
    memset(out,0,sizeof *out);
    out->active=NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier==getpid() && NSApp.active;
    if(!out->active)return;
    out->buttons=(int)NSEvent.pressedMouseButtons;
    CGEventRef cursor=CGEventCreate(NULL);CGPoint point=CGEventGetLocation(cursor);CFRelease(cursor);
    out->x=point.x;out->y=point.y;
    CGFloat primary=NSScreen.screens.firstObject.frame.size.height;
    NSPoint cocoa=NSMakePoint(point.x,primary-point.y);
    NSInteger under=[NSWindow windowNumberAtPoint:cocoa belowWindowWithWindowNumber:0];
    for(NSWindow *window in NSApp.orderedWindows) {
        if(!window.visible || window.miniaturized || window.windowNumber!=under)continue;
        out->window=window.windowNumber;
        NSRect frame=window.frame;out->wx=frame.origin.x;out->wy=primary-NSMaxY(frame);out->width=frame.size.width;out->height=frame.size.height;
        strlcpy(out->title,window.title.UTF8String?:"",sizeof out->title);break;
    }
}
@interface SMUIEventPosition : NSObject
@property NSPoint point;
@end
@implementation SMUIEventPosition
@end
static char positionKey;
static NSPoint eventLocation(id event,SEL selector) {return ((SMUIEventPosition*)objc_getAssociatedObject(event,&positionKey)).point;}
static NSEvent *makeScroll(NSWindow *window,NSPoint screen,double dx,double dy,int phase,BOOL zoom) {
    CGEventRef raw=CGEventCreateScrollWheelEvent(NULL,kCGScrollEventUnitPixel,2,(int32_t)llround(dy),(int32_t)llround(dx));
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventFixedPtDeltaAxis1,dy/10.0);
    CGEventSetDoubleValueField(raw,kCGScrollWheelEventFixedPtDeltaAxis2,dx/10.0);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventIsContinuous,1);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventScrollPhase,phase);
    CGEventSetIntegerValueField(raw,kCGScrollWheelEventMomentumPhase,0);
    CGEventSetIntegerValueField(raw,(CGEventField)51,window.windowNumber);
    CGEventSetFlags(raw,zoom?kCGEventFlagMaskControl:0);
    CGEventSetTimestamp(raw,(uint64_t)(NSProcessInfo.processInfo.systemUptime*1e9));
    CGEventSetLocation(raw,NSPointToCGPoint(screen));
    NSEvent *event=[NSEvent eventWithCGEvent:raw];CFRelease(raw);
    static Class eventClass;static dispatch_once_t once;
    dispatch_once(&once,^{eventClass=objc_allocateClassPair(object_getClass(event),"SpaceMouseUIPluginScrollEvent",0);class_addMethod(eventClass,@selector(locationInWindow),(IMP)eventLocation,"{CGPoint=dd}@:");objc_registerClassPair(eventClass);});
    SMUIEventPosition *position=[SMUIEventPosition new];
    position.point=[window convertPointFromScreen:NSMakePoint(screen.x,NSScreen.screens.firstObject.frame.size.height-screen.y)];
    objc_setAssociatedObject(event,&positionKey,position,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(event,eventClass);
    return event;
}
__attribute__((visibility("default"))) int SMUIScroll(int64_t windowID,double x,double y,double dx,double dy,int phase,int zoom) {
    if(!NSThread.isMainThread || !NSApp.active)return 0;
    NSWindow *window=nil;
    for(NSWindow *candidate in NSApp.windows)if(candidate.windowNumber==windowID && candidate.visible){window=candidate;break;}
    if(!window)return 0;
    NSEvent *event=makeScroll(window,NSMakePoint(x,y),dx,dy,phase,zoom);
    // Entirely local AppKit dispatch: no system event posting or cursor warp.
    NSEvent *hover=[NSEvent mouseEventWithType:NSEventTypeMouseMoved location:event.locationInWindow modifierFlags:0 timestamp:event.timestamp windowNumber:windowID context:nil eventNumber:0 clickCount:0 pressure:0];
    NSView *view=[window.contentView hitTest:event.locationInWindow];
    Class maxon=NSClassFromString(@"MaxonView");
    while(view && maxon && ![view isKindOfClass:maxon])view=view.superview;
    if(!view)view=window.contentView;
    [view mouseMoved:hover];
    [view scrollWheel:event];
    return 1;
}
__attribute__((visibility("default"))) int SMUICompanionRunning(void) {
    return [NSRunningApplication runningApplicationsWithBundleIdentifier:@"local.spacemouse.c4dtrial"].count>0;
}
__attribute__((visibility("default"))) int SMUIImportSettings(char *buffer,int capacity) {
    NSDictionary *old=[NSUserDefaults.standardUserDefaults persistentDomainForName:@"local.spacemouse.c4dtrial"];
    NSMutableDictionary *settings=[NSMutableDictionary new];
    for(NSString *key in @[@"invertHorizontal",@"invertVertical",@"zoomEnabled",@"zoomGain"])
        if(old[key])settings[key]=old[key];
    NSData *data=[NSJSONSerialization dataWithJSONObject:settings options:0 error:nil];
    if(data.length+1>(NSUInteger)capacity)return 0;
    memcpy(buffer,data.bytes,data.length);buffer[data.length]=0;return 1;
}
__attribute__((visibility("default"))) uint64_t SMUISizes(void) {
    return ((uint64_t)sizeof(SMInput)<<32)|(uint64_t)sizeof(SMContext);
}
// Offline-only regression for the shared-client filter. Never used in C4D.
static int testCalls,testFailure;
static BOOL testZero;
static void *testContext;
static ConnexionDeviceState testOriginal;
static void testHandler(unsigned int device,unsigned int message,void *argument,void *context) {
    ++testCalls;
    if(device!=9 || message!=kConnexionMsgDeviceState || context!=testContext)++testFailure;
    ConnexionDeviceState expected=testOriginal;
    if(testZero)memset(expected.axis,0,sizeof expected.axis);
    if(memcmp(argument,&expected,sizeof expected))++testFailure;
}
__attribute__((visibility("default"))) int SMUIForwardingSelfTest(void) {
    if(started || hookedAPI || NSClassFromString(@"MaxonView"))return -1;
    memset(&input,0,sizeof input);memset(&testOriginal,0,sizeof testOriginal);
    input.client=7;input.ready=1;started=YES;suppressed=NO;
    testOriginal.client=7;testOriginal.command=kConnexionCmdHandleAxis;
    for(int i=0;i<6;++i)testOriginal.axis[i]=(int16_t)(20+i*7);
    ConnexionDeviceState packet=testOriginal;
    testCalls=testFailure=0;testZero=NO;testContext=&packet;original4=testHandler;
    forward4(9,kConnexionMsgDeviceState,&packet,testContext);
    if(testCalls!=1)++testFailure;
    for(int i=0;i<6;++i)if(input.axes[i]!=packet.axis[i])++testFailure;
    SMUIClaim(1);testZero=YES;
    forward4(9,kConnexionMsgDeviceState,&packet,testContext);
    if(testCalls!=2)++testFailure;  // One zero report ends vendor motion.
    forward4(9,kConnexionMsgDeviceState,&packet,testContext);
    if(testCalls!=2)++testFailure;  // Remaining UI axes stay local.
    if(memcmp(&packet,&testOriginal,sizeof packet))++testFailure;
    testOriginal.command=packet.command=kConnexionCmdHandleButtons;testZero=NO;
    forward4(9,kConnexionMsgDeviceState,&packet,testContext);
    if(testCalls!=3)++testFailure;  // Buttons always reach the original client.
    SMUIClaim(0);testOriginal.command=packet.command=kConnexionCmdHandleAxis;
    forward4(9,kConnexionMsgDeviceState,&packet,testContext);
    if(testCalls!=4)++testFailure;  // All six original axes pass again.
    started=NO;forward4(9,kConnexionMsgDeviceState,&packet,testContext);
    if(testCalls!=5)++testFailure;
    original4=NULL;memset(&input,0,sizeof input);suppressed=NO;
    return testFailure?0:1;
}
