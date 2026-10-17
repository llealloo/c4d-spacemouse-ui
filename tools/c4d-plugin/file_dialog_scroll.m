// File-dialog scrolling on the existing SpaceMouse input callback.
#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <math.h>
#import <ConnexionClientAPI.h>
#import <objc/runtime.h>
#import <CommonCrypto/CommonDigest.h>
#include <mach-o/dyld.h>
#include <dlfcn.h>
#include <pthread.h>
#include <string.h>
typedef void (*Handler3)(unsigned int,unsigned int,void*);
typedef void (*Handler4)(unsigned int,unsigned int,void*,void*);
static Handler3 previous3;static Handler4 previous4;static void **slot;
static id apiObject;static uint16_t client;
static NSTimer *timer;static NSMutableArray *observers;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static BOOL active,dialog,waitingNeutral,zeroSent;
static uint64_t detected,blocked,stops,passed;

static double scrollAxes[6],axisTime,previousTick;static double dialogScrollSpeed=3600,dialogHorizontalSpeed=2400;static BOOL dialogInvertVertical=YES;
static uint64_t scrollEvents,gestureStarts;static BOOL scrolling;static double remainderX,remainderY,lastMovement;static NSInteger gestureWindow;
static void scrollTick(void);
#ifdef SM_FILE_DIALOG_TEST
static int testDialog=-1;
#endif
static BOOL panel(NSWindow *window) {
 return window && window.visible && [window isKindOfClass:NSSavePanel.class];
}
static void updateDialog(void) {
 if(!NSThread.isMainThread)return;
 BOOL found=panel(NSApp.modalWindow);
 for(NSWindow *window in NSApp.windows)if(panel(window)||panel(window.attachedSheet)){found=YES;break;}
#ifdef SM_FILE_DIALOG_TEST
 if(testDialog>=0)found=testDialog;
#endif
 pthread_mutex_lock(&lock);
 if(active && found!=dialog) {
  dialog=found;
  if(found){++detected;zeroSent=NO;waitingNeutral=NO;memset(scrollAxes,0,sizeof scrollAxes);axisTime=0;}
 }
 pthread_mutex_unlock(&lock);
}
static BOOL consume(unsigned int message,void *argument,ConnexionDeviceState *zero,BOOL *sendZero) {
 *sendZero=NO;
 if(message!=kConnexionMsgDeviceState || !argument)return NO;
 ConnexionDeviceState *state=argument;
 if(state->client!=client || state->command!=kConnexionCmdHandleAxis)return NO;
 if(NSThread.isMainThread)updateDialog();
 pthread_mutex_lock(&lock);
 BOOL stop=active && (dialog||waitingNeutral);
 if(stop) {
  ++blocked;
  if(!zeroSent){*zero=*state;memset(zero->axis,0,sizeof zero->axis);*sendZero=YES;zeroSent=YES;++stops;}
  BOOL neutral=YES;for(int i=0;i<6;++i)if(abs(state->axis[i])>3){neutral=NO;break;}
  if(dialog){waitingNeutral=!neutral;for(int i=0;i<6;++i)scrollAxes[i]=state->axis[i];axisTime=NSProcessInfo.processInfo.systemUptime;}
  else if(neutral){waitingNeutral=NO;zeroSent=NO;}
 }else ++passed;
 pthread_mutex_unlock(&lock);return stop;
}
static void forward3(unsigned int device,unsigned int message,void *argument) {
 Handler3 original=__atomic_load_n(&previous3,__ATOMIC_ACQUIRE);if(!original)return;
 ConnexionDeviceState zero;BOOL sendZero;
 if(!consume(message,argument,&zero,&sendZero))original(device,message,argument);
 else if(sendZero)original(device,message,&zero);
}
static void forward4(unsigned int device,unsigned int message,void *argument,void *context) {
 Handler4 original=__atomic_load_n(&previous4,__ATOMIC_ACQUIRE);if(!original)return;
 ConnexionDeviceState zero;BOOL sendZero;
 if(!consume(message,argument,&zero,&sendZero))original(device,message,argument,context);
 else if(sendZero)original(device,message,&zero,context);
}
static double response(double value) {
 double magnitude=fmin(fabs(value)/350.0,1.0);
 return magnitude<=.01?0:copysign((magnitude-.01)/.99,value);
}
static void scrollTick(void) {
 double now=NSProcessInfo.processInfo.systemUptime;
 double dt=previousTick?fmin(now-previousTick,.03):.01;previousTick=now;
 pthread_mutex_lock(&lock);
 BOOL allowed=active && dialog && axisTime>0;
 double horizontal=response(scrollAxes[0]),vertical=response(scrollAxes[2]);
 // Suppress incidental cross-axis motion before unequal gains can amplify it.
 if(fabs(horizontal)>fabs(vertical)*1.4)vertical=0;
 else if(fabs(vertical)>fabs(horizontal)*1.4)horizontal=0;
 double dx=horizontal*dialogHorizontalSpeed*dt,dy=(dialogInvertVertical?1:-1)*vertical*dialogScrollSpeed*dt;
 pthread_mutex_unlock(&lock);
 NSWindow *target=NSApp.modalWindow;
 if(!panel(target)) {target=nil;for(NSWindow *window in NSApp.windows)if(panel(window)){target=window;break;}else if(panel(window.attachedSheet)){target=window.attachedSheet;break;}}
 NSPoint mouse=NSEvent.mouseLocation;
 BOOL inside=target && NSPointInRect(mouse,target.frame);
 BOOL eligible=allowed && NSApp.active && inside && !(NSEvent.pressedMouseButtons);
 BOOL moving=eligible && CGPreflightPostEventAccess() && (dx!=0||dy!=0);
 if(!target || !NSApp.active || !inside){scrolling=NO;remainderX=remainderY=0;pthread_mutex_lock(&lock);memset(scrollAxes,0,sizeof scrollAxes);axisTime=0;pthread_mutex_unlock(&lock);return;}
 if(gestureWindow!=target.windowNumber){scrolling=NO;remainderX=remainderY=0;gestureWindow=target.windowNumber;}
 double px=0,py=0;
 if(moving){lastMovement=now;remainderX+=dx;remainderY+=dy;px=trunc(remainderX);py=trunc(remainderY);remainderX-=px;remainderY-=py;}
 BOOL ending=scrolling && (!eligible || (!moving && now-lastMovement>.20));
 if(px==0 && py==0 && !ending)return;
 int phase=ending?4:(scrolling?2:1);
 if(!ending && !scrolling)++gestureStarts;
 // The remote file browser receives the window's normal event dispatch.
 // Accumulate subpixels before crossing that serialization boundary.
 // NSBrowser can prioritize vertical deltas when both axes share one packet.
 // Deliver pure-axis pixel packets so incidental cross-axis input cannot swallow X.
 for(int axis=0;axis<2;++axis) {
  int32_t vertical=axis==0&&!ending?(int32_t)py:0;
  int32_t horizontal=axis==1&&!ending?(int32_t)px:0;
  if(!vertical && !horizontal)continue;
  CGEventRef raw=CGEventCreateScrollWheelEvent(NULL,kCGScrollEventUnitPixel,2,vertical,horizontal);
  if(!raw)continue;
  CGEventSetIntegerValueField(raw,kCGScrollWheelEventIsContinuous,1);
  CGEventSetIntegerValueField(raw,kCGScrollWheelEventScrollPhase,0);
  CGEventSetIntegerValueField(raw,kCGScrollWheelEventMomentumPhase,0);
  CGEventSetLocation(raw,CGPointMake(mouse.x,NSScreen.screens.firstObject.frame.size.height-mouse.y));
  CGEventSetFlags(raw,0);
  if(CGPreflightPostEventAccess()){CGEventPost(kCGHIDEventTap,raw);++scrollEvents;}
  CFRelease(raw);
 }
 scrolling=!ending;
 (void)phase;
 if(ending)remainderX=remainderY=0;
}
static BOOL digestMatches(NSString *path,NSString *expected) {
 NSData *data=[NSData dataWithContentsOfFile:path];if(!data)return NO;
 unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
 NSMutableString *hash=[NSMutableString new];for(int i=0;i<CC_SHA256_DIGEST_LENGTH;++i)[hash appendFormat:@"%02x",digest[i]];
 return [hash isEqualToString:expected];
}
__attribute__((visibility("default"))) int SMFileDialogStart(uint16_t clientID) {
 if(!NSThread.isMainThread || !clientID)return -1;if(active)return 0;
 Dl_info location;if(!dladdr((void*)&ConnexionClientControl,&location))return -2;
 if(!digestMatches(@(location.dli_fname),@"377cb3a9efda8a9496e202dce33055f7d1908d51e9e069d07419b6c8d442ae07"))return -2;
 Class cls=NSClassFromString(@"ConnexionClientAPI");
 Ivar a=class_getInstanceVariable(cls,"deviceMessageHandler"),b=class_getInstanceVariable(cls,"deviceMessageHandler2");
 if(!a||!b||ivar_getOffset(a)!=32||ivar_getOffset(b)!=56||class_getInstanceSize(cls)!=5096)return -3;
 uintptr_t base=(uintptr_t)location.dli_fbase;
 NSDictionary *registry=(__bridge NSDictionary*)*(void**)(base+0x1c0c0);if(!registry)return -3;
 id candidate;@synchronized(registry){candidate=registry[@(clientID)][@"object"];}
 if(![candidate isKindOfClass:cls])return -3;
 id info=[candidate valueForKey:@"applicationInfo"];
 if(![[info valueForKey:@"clientName"] isEqualToString:@"Cinema4d"] || ![[info valueForKey:@"bundleid"] isEqualToString:@"net.maxon.cinema4d"])return -3;
 void *standard=__atomic_load_n((void**)((__bridge void*)candidate+32),__ATOMIC_ACQUIRE);
 void *extended=__atomic_load_n((void**)((__bridge void*)candidate+56),__ATOMIC_ACQUIRE);
 void *callback=standard?:extended;Dl_info owner;
 if(!callback||!dladdr(callback,&owner)||!strstr(owner.dli_fname?:"","libSpaceMouseUIInput.dylib"))return -4;
 if(!digestMatches(@(owner.dli_fname),@"ba9885f74067c5f2d15f481816136fa2ac549f5903075fe151c32c68eb9caecd"))return -4;
 slot=(void**)((__bridge void*)candidate+(standard?32:56));client=clientID;
 if(standard)__atomic_store_n(&previous3,(Handler3)callback,__ATOMIC_RELEASE);
 else __atomic_store_n(&previous4,(Handler4)callback,__ATOMIC_RELEASE);
 void *expected=callback;
 if(!__atomic_compare_exchange_n(slot,&expected,standard?(void*)&forward3:(void*)&forward4,NO,__ATOMIC_RELEASE,__ATOMIC_RELAXED)){slot=NULL;return -5;}
 apiObject=candidate;active=YES;dialog=NO;waitingNeutral=NO;zeroSent=NO;
 observers=[NSMutableArray new];
 for(NSNotificationName name in @[NSWindowDidBecomeKeyNotification,NSWindowWillBeginSheetNotification,NSWindowDidEndSheetNotification,NSWindowWillCloseNotification]) {
  [observers addObject:[NSNotificationCenter.defaultCenter addObserverForName:name object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note){updateDialog();}]];
 }
 timer=[NSTimer timerWithTimeInterval:.01 repeats:YES block:^(NSTimer *unused){updateDialog();scrollTick();}];
 [NSRunLoop.mainRunLoop addTimer:timer forMode:NSRunLoopCommonModes];
 [NSRunLoop.mainRunLoop addTimer:timer forMode:NSModalPanelRunLoopMode];
 updateDialog();return 0;
}
__attribute__((visibility("default"))) void SMFileDialogStop(void) {
 if(!NSThread.isMainThread)return;
 [timer invalidate];timer=nil;scrolling=NO;previousTick=0;
 for(id observer in observers)[NSNotificationCenter.defaultCenter removeObserver:observer];observers=nil;
 if(slot){void *current=__atomic_load_n(slot,__ATOMIC_ACQUIRE);void *expected=current;
  if(current==(void*)&forward3)__atomic_compare_exchange_n(slot,&expected,(void*)previous3,NO,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
  else if(current==(void*)&forward4)__atomic_compare_exchange_n(slot,&expected,(void*)previous4,NO,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
 }
 slot=NULL;apiObject=nil;pthread_mutex_lock(&lock);active=NO;dialog=NO;waitingNeutral=NO;pthread_mutex_unlock(&lock);
}
__attribute__((visibility("default"))) void SMFileDialogRead(uint64_t *result) {
 if(NSThread.isMainThread)updateDialog();pthread_mutex_lock(&lock);
 result[0]=active;result[1]=dialog;result[2]=waitingNeutral;result[3]=detected;result[4]=blocked;result[5]=stops;result[6]=passed;
 pthread_mutex_unlock(&lock);
}

#ifdef SM_FILE_DIALOG_TEST
static int fakeCalls;static int fakeAxis;
static void fakeHandler(unsigned int device,unsigned int message,void *argument) {
 ++fakeCalls;fakeAxis=((ConnexionDeviceState*)argument)->axis[0];
}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
__attribute__((visibility("default"))) int SMFileDialogSelfTest(void) {
 ConnexionDeviceState packet;memset(&packet,0,sizeof packet);
 packet.client=7;packet.command=kConnexionCmdHandleAxis;packet.axis[0]=100;
 client=7;active=YES;testDialog=0;previous3=fakeHandler;
 forward3(0,kConnexionMsgDeviceState,&packet);CHECK(fakeCalls==1 && fakeAxis==100);
 testDialog=1;forward3(0,kConnexionMsgDeviceState,&packet);CHECK(fakeCalls==2 && fakeAxis==0 && waitingNeutral);
 forward3(0,kConnexionMsgDeviceState,&packet);CHECK(fakeCalls==2 && blocked==2);
 packet.command=kConnexionCmdHandleButtons;forward3(0,kConnexionMsgDeviceState,&packet);CHECK(fakeCalls==3);
 packet.command=kConnexionCmdHandleAxis;packet.client=8;forward3(0,kConnexionMsgDeviceState,&packet);CHECK(fakeCalls==4);
 packet.client=7;testDialog=0;forward3(0,kConnexionMsgDeviceState,&packet);CHECK(fakeCalls==4 && waitingNeutral);
 memset(packet.axis,0,sizeof packet.axis);forward3(0,kConnexionMsgDeviceState,&packet);CHECK(!waitingNeutral);
 packet.axis[0]=100;forward3(0,kConnexionMsgDeviceState,&packet);CHECK(fakeCalls==5 && fakeAxis==100);
 SMFileDialogStop();CHECK(!active && !dialog && !waitingNeutral);return 0;
}
#endif

__attribute__((visibility("default"))) int SMDialogPostAccess(void){return CGPreflightPostEventAccess();}

__attribute__((visibility("default"))) int SMDialogConfigureScroll(double speed,int invertVertical){if(!NSThread.isMainThread||!isfinite(speed)||speed<50||speed>20000)return 0;dialogScrollSpeed=speed;dialogInvertVertical=!!invertVertical;return 1;}

__attribute__((visibility("default"))) int SMDialogConfigureAxes(double horizontal,double vertical){if(!NSThread.isMainThread||!isfinite(horizontal)||!isfinite(vertical)||horizontal<50||horizontal>20000||vertical<50||vertical>20000)return 0;dialogHorizontalSpeed=horizontal;dialogScrollSpeed=vertical;return 1;}
