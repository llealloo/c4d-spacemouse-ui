// Bounded external-process test using only public 3Dconnexion APIs.
#import <AppKit/AppKit.h>
#import <ConnexionClientAPI.h>
#include <signal.h>
static volatile sig_atomic_t stopRequested;
static uint64_t activations,deactivations;
static void onSignal(int ignored){stopRequested=1;}
static void message(unsigned int device,unsigned int type,void *argument){}
static void report(NSString *path,uint16_t client,BOOL enabled,int error) {
 NSDictionary *data=@{@"client":@(client),@"override":@(enabled),@"error":@(error),@"bundle":NSBundle.mainBundle.bundleIdentifier?:@"",@"pid":@(NSProcessInfo.processInfo.processIdentifier),@"activations":@(activations),@"deactivations":@(deactivations)};
 [[NSJSONSerialization dataWithJSONObject:data options:0 error:nil] writeToFile:path atomically:YES];
}
int main(int argc,const char **argv){@autoreleasepool{
 if(argc!=4)return 2;
 NSString *gate=@(argv[1]),*status=@(argv[2]);double duration=atof(argv[3]);
 if(duration<=0||duration>3600)return 2;
 signal(SIGTERM,onSignal);signal(SIGINT,onSignal);
 [NSApplication sharedApplication];
 int error=SetConnexionHandlers(message,NULL,NULL,true);if(error){report(status,0,NO,error);return 3;}
 // Dedicated background bundle identity cannot match Cinema 4D's settings.
 const char *label="";uint8_t name[256]={0};name[0]=(uint8_t)strlen(label);memcpy(name+1,label,name[0]);
 uint16_t client=0;BOOL enabled=NO;double end=NSProcessInfo.processInfo.systemUptime+duration;
 report(status,0,NO,0);
 while(!stopRequested && NSProcessInfo.processInfo.systemUptime<end){@autoreleasepool{
  NSDictionary *state=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:gate]?:[NSData data] options:0 error:nil];
  NSDictionary *attrs=[NSFileManager.defaultManager attributesOfItemAtPath:gate error:nil];
  BOOL fresh=attrs && -[attrs[NSFileModificationDate] timeIntervalSinceNow]<2;
  BOOL foreground=[NSWorkspace.sharedWorkspace.frontmostApplication.bundleIdentifier isEqualToString:@"net.maxon.cinema4d"];
  BOOL wanted=fresh && foreground && [state[@"active"] boolValue] && [state[@"dialog"] boolValue];
  if(wanted && !client){client=RegisterConnexionClient(kConnexionClientManual,name,kConnexionClientModePlugin,0);if(!client){error=-100;stopRequested=1;}}
  if(wanted!=enabled && client){int32_t result=0;error=ConnexionClientControl(client,wanted?kConnexionCtlActivateClient:kConnexionCtlDeactivateClient,0,&result);if(!error){enabled=wanted;if(wanted)++activations;else ++deactivations;}else stopRequested=1;report(status,client,enabled,error);}
  [NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.05]];
 }}
 if(client){int32_t result=0;ConnexionClientControl(client,kConnexionCtlDeactivateClient,0,&result);UnregisterConnexionClient(client);}
 CleanupConnexionHandlers();report(status,0,NO,error);return error?4:0;
}}
