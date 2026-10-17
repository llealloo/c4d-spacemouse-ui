import AppKit
import CoreGraphics
import Foundation
import IOKit.hid

private let vendorID = 0x256F
private let genericDesktopPage = 0x01
private let multiAxisControllerUsage = 0x08
private let buttonPage = 0x09
private let injectedEventTag: Int64 = 0x5350_4D4F_5553_4501
private let finderBundleIdentifier = "com.apple.finder"

private enum Axis: Int, CaseIterable {
    case x = 0x30
    case y = 0x31
    case z = 0x32
    case rx = 0x33
    case ry = 0x34
    case rz = 0x35

    var label: String {
        switch self {
        case .x: "X"
        case .y: "Y"
        case .z: "Z"
        case .rx: "Rx"
        case .ry: "Ry"
        case .rz: "Rz"
        }
    }
}

private struct Options {
    var smoothScroll = false
    var observeScroll = false
    var seize = false
    var legacyScroll = false
    var verticalAxis: Axis = .z
    var maxSpeed = 1_400.0
    var deadZone = 0.055
    var curve = 1.65
    var logHz = 10.0
    var duration: TimeInterval?
    var invertX = false
    var invertY = false

    static func parse(_ arguments: [String]) throws -> Options {
        var options = Options()
        var index = 0

        func value(after flag: String) throws -> String {
            guard index + 1 < arguments.count else {
                throw ProbeError.usage("Missing value after \(flag)")
            }
            index += 1
            return arguments[index]
        }

        while index < arguments.count {
            let argument = arguments[index]
            switch argument {
            case "--smooth-scroll": options.smoothScroll = true
            case "--observe-scroll": options.observeScroll = true
            case "--seize": options.seize = true
            case "--legacy-scroll": options.legacyScroll = true
            case "--invert-x": options.invertX = true
            case "--invert-y": options.invertY = true
            case "--vertical-axis":
                let name = try value(after: argument).lowercased()
                guard let axis = Axis.allCases.first(where: { $0.label.lowercased() == name }), axis == .y || axis == .z else {
                    throw ProbeError.usage("--vertical-axis must be y or z")
                }
                options.verticalAxis = axis
            case "--max-speed":
                guard let number = Double(try value(after: argument)), number > 0 else {
                    throw ProbeError.usage("--max-speed must be greater than zero")
                }
                options.maxSpeed = number
            case "--dead-zone":
                guard let number = Double(try value(after: argument)), (0..<0.5).contains(number) else {
                    throw ProbeError.usage("--dead-zone must be between 0 and 0.5")
                }
                options.deadZone = number
            case "--curve":
                guard let number = Double(try value(after: argument)), number > 0 else {
                    throw ProbeError.usage("--curve must be greater than zero")
                }
                options.curve = number
            case "--log-hz":
                guard let number = Double(try value(after: argument)), number >= 0 else {
                    throw ProbeError.usage("--log-hz must be zero or greater")
                }
                options.logHz = number
            case "--duration":
                guard let number = Double(try value(after: argument)), number > 0 else {
                    throw ProbeError.usage("--duration must be greater than zero")
                }
                options.duration = number
            case "--help", "-h":
                printHelp()
                exit(EXIT_SUCCESS)
            default:
                throw ProbeError.usage("Unknown argument: \(argument)")
            }
            index += 1
        }
        return options
    }
}

private enum ProbeError: Error, CustomStringConvertible {
    case usage(String)
    case setup(String)

    var description: String {
        switch self {
        case .usage(let message), .setup(let message): message
        }
    }
}

private struct AxisReading {
    var raw = 0
    var normalized = 0.0
    var logicalMin = 0
    var logicalMax = 0
}

private final class SpaceMouseProbe {
    private let options: Options
    private let manager: IOHIDManager
    private var readings = Dictionary(uniqueKeysWithValues: Axis.allCases.map { ($0, AxisReading()) })
    private var buttons: Set<Int> = []
    private var connectedDevices: Set<IOHIDDevice> = []
    private var lastInputTime = ProcessInfo.processInfo.systemUptime
    private var lastLogTime = 0.0
    private var stateChanged = false
    private var tickTimer: Timer?
    private var stopTimer: Timer?
    private var signalSource: DispatchSourceSignal?
    private var eventTap: CFMachPort?
    private var eventTapSource: CFRunLoopSource?
    private var scrolling = false
    private var lastTickTime = ProcessInfo.processInfo.systemUptime
    private var hidOpened = false
    private var pixelRemainderX = 0.0
    private var pixelRemainderY = 0.0
    private var gestureUsesLegacyScroll = false

    init(options: Options) {
        self.options = options
        self.manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
    }

    func run() throws {
        printBanner()
        configureHIDManager()

        if options.observeScroll {
            try configureScrollObserver()
        }
        if options.smoothScroll {
            guard CGPreflightPostEventAccess() || CGRequestPostEventAccess() else {
                throw ProbeError.setup("Event posting is not authorized. Enable this executable in System Settings > Privacy & Security > Accessibility, then run it again.")
            }
        }

        let openOptions = options.seize ? IOOptionBits(kIOHIDOptionsTypeSeizeDevice) : IOOptionBits(kIOHIDOptionsTypeNone)
        let result = IOHIDManagerOpen(manager, openOptions)
        if result == kIOReturnSuccess {
            hidOpened = true
        } else if result == kIOReturnExclusiveAccess, options.observeScroll, !options.smoothScroll, !options.seize {
            print("HID input unavailable: 3Dconnexion holds the device exclusively.")
            print("Continuing in scroll-observer-only mode.\n")
        } else {
            if result == kIOReturnExclusiveAccess {
                throw ProbeError.setup("The SpaceMouse is already open exclusively (kIOReturnExclusiveAccess). Quit 3DconnexionHelper, then retry.")
            }
            if result == kIOReturnNotPermitted {
                throw ProbeError.setup("macOS denied HID access (kIOReturnNotPermitted). Run the built executable outside an application sandbox.")
            }
            throw ProbeError.setup(String(format: "Could not open HID manager (0x%08X).", result))
        }

        let interval = options.smoothScroll ? 0.008 : 0.02
        lastTickTime = ProcessInfo.processInfo.systemUptime
        tickTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            self?.tick()
        }

        if let duration = options.duration {
            stopTimer = Timer.scheduledTimer(withTimeInterval: duration, repeats: false) { [weak self] _ in
                self?.stop()
            }
        }

        signal(SIGINT, SIG_IGN)
        let signalSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
        signalSource.setEventHandler { [weak self] in self?.stop() }
        signalSource.resume()
        self.signalSource = signalSource

        CFRunLoopRun()
    }

    private func configureHIDManager() {
        let matching: [String: Any] = [
            kIOHIDVendorIDKey as String: vendorID,
            kIOHIDDeviceUsagePageKey as String: genericDesktopPage,
            kIOHIDDeviceUsageKey as String: multiAxisControllerUsage
        ]
        IOHIDManagerSetDeviceMatching(manager, matching as CFDictionary)

        let context = Unmanaged.passUnretained(self).toOpaque()
        IOHIDManagerRegisterDeviceMatchingCallback(manager, { context, _, _, device in
            guard let context else { return }
            Unmanaged<SpaceMouseProbe>.fromOpaque(context).takeUnretainedValue().deviceMatched(device)
        }, context)
        IOHIDManagerRegisterDeviceRemovalCallback(manager, { context, _, _, device in
            guard let context else { return }
            Unmanaged<SpaceMouseProbe>.fromOpaque(context).takeUnretainedValue().deviceRemoved(device)
        }, context)
        IOHIDManagerRegisterInputValueCallback(manager, { context, result, _, value in
            guard result == kIOReturnSuccess, let context else { return }
            Unmanaged<SpaceMouseProbe>.fromOpaque(context).takeUnretainedValue().inputValue(value)
        }, context)
        IOHIDManagerScheduleWithRunLoop(manager, CFRunLoopGetMain(), CFRunLoopMode.commonModes.rawValue)
    }

    private func configureScrollObserver() throws {
        guard CGPreflightListenEventAccess() || CGRequestListenEventAccess() else {
            throw ProbeError.setup("Event listening is not authorized. Enable this executable in System Settings > Privacy & Security > Input Monitoring, then run it again.")
        }

        let mask = CGEventMask(1) << CGEventType.scrollWheel.rawValue
        let context = Unmanaged.passUnretained(self).toOpaque()
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,
            eventsOfInterest: mask,
            callback: { _, type, event, context in
                guard type == .scrollWheel, let context else { return Unmanaged.passUnretained(event) }
                Unmanaged<SpaceMouseProbe>.fromOpaque(context).takeUnretainedValue().observedScroll(event)
                return Unmanaged.passUnretained(event)
            },
            userInfo: context
        ) else {
            throw ProbeError.setup("Could not create the scroll event tap.")
        }

        eventTap = tap
        let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        eventTapSource = source
        CFRunLoopAddSource(CFRunLoopGetMain(), source, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
    }

    private func deviceMatched(_ device: IOHIDDevice) {
        connectedDevices.insert(device)
        let product = property(device, kIOHIDProductKey) ?? "Unknown device"
        let transport = property(device, kIOHIDTransportKey) ?? "Unknown transport"
        let productID = integerProperty(device, kIOHIDProductIDKey)
        let reportInterval = integerProperty(device, kIOHIDReportIntervalKey)
        print(String(format: "Connected: %@ (VID %04X, PID %04X, %@, report interval %@ us)", product, vendorID, productID, transport, reportInterval == 0 ? "unknown" : String(reportInterval)))
    }

    private func deviceRemoved(_ device: IOHIDDevice) {
        connectedDevices.remove(device)
        if connectedDevices.isEmpty {
            for axis in Axis.allCases {
                readings[axis] = AxisReading()
            }
            buttons.removeAll()
        }
        print("Disconnected: \(property(device, kIOHIDProductKey) ?? "SpaceMouse")")
    }

    private func inputValue(_ value: IOHIDValue) {
        let element = IOHIDValueGetElement(value)
        let usagePage = Int(IOHIDElementGetUsagePage(element))
        let usage = Int(IOHIDElementGetUsage(element))
        let raw = IOHIDValueGetIntegerValue(value)

        if usagePage == genericDesktopPage, let axis = Axis(rawValue: usage) {
            let logicalMin = IOHIDElementGetLogicalMin(element)
            let logicalMax = IOHIDElementGetLogicalMax(element)
            let normalized = normalize(raw, minimum: logicalMin, maximum: logicalMax)
            readings[axis] = AxisReading(raw: raw, normalized: normalized, logicalMin: logicalMin, logicalMax: logicalMax)
            lastInputTime = ProcessInfo.processInfo.systemUptime
            stateChanged = true
        } else if usagePage == buttonPage {
            if raw == 0 { buttons.remove(usage) } else { buttons.insert(usage) }
            stateChanged = true
        }
    }

    private func tick() {
        let now = ProcessInfo.processInfo.systemUptime
        let dt = min(max(now - lastTickTime, 0), 0.05)
        lastTickTime = now

        if options.smoothScroll {
            postSmoothScroll(dt: dt)
        }
        if options.logHz > 0, stateChanged, now - lastLogTime >= 1.0 / options.logHz {
            logState(now: now)
            lastLogTime = now
            stateChanged = false
        }
    }

    private func postSmoothScroll(dt: TimeInterval) {
        let x = response(readings[.x]?.normalized ?? 0)
        let y = response(readings[options.verticalAxis]?.normalized ?? 0)
        let directionX = options.invertX ? -1.0 : 1.0
        let directionY = options.invertY ? -1.0 : 1.0
        let dx = x * options.maxSpeed * dt * directionX
        let dy = y * options.maxSpeed * dt * directionY
        let active = abs(dx) >= 0.001 || abs(dy) >= 0.001

        if active {
            if !scrolling {
                gestureUsesLegacyScroll = options.legacyScroll || frontmostApplicationIsFinder()
            }
            pixelRemainderX += dx
            pixelRemainderY += dy
            let pixelX = pixelRemainderX.rounded(.towardZero)
            let pixelY = pixelRemainderY.rounded(.towardZero)
            pixelRemainderX -= pixelX
            pixelRemainderY -= pixelY

            if gestureUsesLegacyScroll {
                postScroll(dx: pixelX, dy: pixelY, phase: [])
            } else if scrolling {
                postScroll(dx: pixelX, dy: pixelY, phase: .changed)
            } else {
                // Trackpads announce a potential gesture before locking its
                // target view. Finder relies on this more than browsers do.
                postScroll(dx: 0, dy: 0, phase: .mayBegin)
                postScroll(dx: pixelX, dy: pixelY, phase: .began)
            }
            scrolling = true
        } else if scrolling {
            if !gestureUsesLegacyScroll {
                postScroll(dx: 0, dy: 0, phase: .ended)
            }
            scrolling = false
            pixelRemainderX = 0
            pixelRemainderY = 0
        }
    }

    private func postScroll(dx: Double, dy: Double, phase: NSEvent.Phase) {
        guard let event = CGEvent(
            scrollWheelEvent2Source: nil,
            units: .pixel,
            wheelCount: 2,
            wheel1: Int32(dy.rounded()),
            wheel2: Int32(dx.rounded()),
            wheel3: 0
        ) else { return }

        event.setIntegerValueField(.eventSourceUserData, value: injectedEventTag)
        event.setIntegerValueField(.scrollWheelEventIsContinuous, value: 1)
        event.setIntegerValueField(.scrollWheelEventScrollPhase, value: coreGraphicsScrollPhase(for: phase))
        event.setIntegerValueField(.scrollWheelEventMomentumPhase, value: 0)
        event.post(tap: .cghidEventTap)
    }

    private func observedScroll(_ event: CGEvent) {
        let marker = event.getIntegerValueField(.eventSourceUserData) == injectedEventTag ? " ours" : ""
        let own = marker + String(format: " t=%.6f control=%d tag=%llx",
                                  Double(event.timestamp) / 1_000_000_000,
                                  event.flags.contains(.maskControl) ? 1 : 0,
                                  event.getIntegerValueField(.eventSourceUserData))
        let appKitEvent = NSEvent(cgEvent: event)
        let dy = event.getDoubleValueField(.scrollWheelEventFixedPtDeltaAxis1)
        let dx = event.getDoubleValueField(.scrollWheelEventFixedPtDeltaAxis2)
        let pointY = event.getIntegerValueField(.scrollWheelEventPointDeltaAxis1)
        let pointX = event.getIntegerValueField(.scrollWheelEventPointDeltaAxis2)
        let continuous = event.getIntegerValueField(.scrollWheelEventIsContinuous)
        let cgPhase = event.getIntegerValueField(.scrollWheelEventScrollPhase)
        let cgMomentum = event.getIntegerValueField(.scrollWheelEventMomentumPhase)
        let scrollCount = event.getIntegerValueField(.scrollWheelEventScrollCount)
        let nsPhase = appKitEvent?.phase.rawValue ?? 0
        let nsMomentum = appKitEvent?.momentumPhase.rawValue ?? 0
        let precise = appKitEvent?.hasPreciseScrollingDeltas == true ? 1 : 0
        let pid = event.getIntegerValueField(.eventSourceUnixProcessID)
        print(String(format: "SCROLL%@ fixed=(%7.3f,%7.3f) point=(%4lld,%4lld) continuous=%lld precise=%d phase=%lld/%lu momentum=%lld/%lu count=%lld pid=%lld", own, dx, dy, pointX, pointY, continuous, precise, cgPhase, nsPhase, cgMomentum, nsMomentum, scrollCount, pid))
    }

    private func response(_ value: Double) -> Double {
        let magnitude = abs(value)
        guard magnitude > options.deadZone else { return 0 }
        let scaled = min(1, (magnitude - options.deadZone) / (1 - options.deadZone))
        return copysign(pow(scaled, options.curve), value)
    }

    private func logState(now: TimeInterval) {
        let values = Axis.allCases.map { axis -> String in
            let reading = readings[axis] ?? AxisReading()
            return String(format: "%@=%4d (% .3f)", axis.label, reading.raw, reading.normalized)
        }.joined(separator: "  ")
        let buttonText = buttons.isEmpty ? "-" : buttons.sorted().map(String.init).joined(separator: ",")
        print(String(format: "HID %@  buttons=%@  age=%4.0f ms", values, buttonText, (now - lastInputTime) * 1_000))
    }

    private func stop() {
        if scrolling, !gestureUsesLegacyScroll {
            postScroll(dx: 0, dy: 0, phase: .ended)
        }
        scrolling = false
        tickTimer?.invalidate()
        stopTimer?.invalidate()
        if let eventTapSource {
            CFRunLoopRemoveSource(CFRunLoopGetMain(), eventTapSource, .commonModes)
        }
        IOHIDManagerUnscheduleFromRunLoop(manager, CFRunLoopGetMain(), CFRunLoopMode.commonModes.rawValue)
        if hidOpened {
            IOHIDManagerClose(manager, IOOptionBits(kIOHIDOptionsTypeNone))
        }
        print("Stopped.")
        CFRunLoopStop(CFRunLoopGetMain())
    }

    private func printBanner() {
        print("SpaceMouse probe")
        print("  HID logging: on")
        print("  Scroll observer: \(options.observeScroll ? "on" : "off")")
        print("  Smooth scroll injection: \(options.smoothScroll ? "on" : "off")")
        print("  Gesture phases: \(options.legacyScroll ? "off (legacy continuous mode)" : "on")")
        if !options.legacyScroll {
            print("  Automatic profile: Finder uses legacy continuous mode")
        }
        print("  Exclusive device access: \(options.seize ? "on" : "off")")
        if options.smoothScroll {
            print("  Mapping: X -> horizontal, \(options.verticalAxis.label) -> vertical, max \(Int(options.maxSpeed)) px/s")
        }
        print("Press Control-C to stop.\n")
    }
}

private func frontmostApplicationIsFinder() -> Bool {
    NSWorkspace.shared.frontmostApplication?.bundleIdentifier == finderBundleIdentifier
}

private func normalize(_ value: Int, minimum: Int, maximum: Int) -> Double {
    guard maximum > minimum else { return 0 }
    if minimum < 0, maximum > 0 {
        return value >= 0 ? min(1, Double(value) / Double(maximum)) : max(-1, Double(value) / Double(-minimum))
    }
    let midpoint = Double(minimum + maximum) / 2
    let halfRange = Double(maximum - minimum) / 2
    return max(-1, min(1, (Double(value) - midpoint) / halfRange))
}

// CGEvent's scroll-phase field uses 1/2/4 for began/changed/ended. Those are
// not the same raw values as NSEvent.Phase (1/4/8).
private func coreGraphicsScrollPhase(for phase: NSEvent.Phase) -> Int64 {
    if phase.contains(.began) { return 1 }
    if phase.contains(.changed) { return 2 }
    if phase.contains(.ended) { return 4 }
    if phase.contains(.cancelled) { return 8 }
    if phase.contains(.mayBegin) { return 128 }
    return 0
}

private func property(_ device: IOHIDDevice, _ key: String) -> String? {
    IOHIDDeviceGetProperty(device, key as CFString).map { String(describing: $0) }
}

private func integerProperty(_ device: IOHIDDevice, _ key: String) -> Int {
    guard let value = IOHIDDeviceGetProperty(device, key as CFString) else { return 0 }
    if CFGetTypeID(value) == CFNumberGetTypeID() {
        return (value as! NSNumber).intValue
    }
    return 0
}

private func printHelp() {
    print("""
    Usage: spacemouse-probe [options]

      (no flags)              Log raw and normalized six-axis HID values.
      --observe-scroll        Log all system scroll events and their precision fields.
      --smooth-scroll         Post continuous two-axis pixel scrolling from the cap.
      --seize                 Open the SpaceMouse exclusively to suppress packaged mappings.
      --legacy-scroll         Send continuous pixel deltas without gesture phases.
      --vertical-axis y|z     Choose the cap axis used for vertical scrolling (default: z).
      --max-speed NUMBER      Maximum scroll velocity in pixels/second (default: 1400).
      --dead-zone NUMBER      Normalized center dead zone (default: 0.055).
      --curve NUMBER          Response exponent (default: 1.65).
      --invert-x              Reverse horizontal scrolling.
      --invert-y              Reverse vertical scrolling.
      --log-hz NUMBER         HID log rate; zero disables value logs (default: 10).
      --duration SECONDS      Stop automatically after a test interval.
      --help                  Show this help.

    Start without --smooth-scroll or --seize. Those modes are explicitly opt-in.
    """)
}

do {
    let options = try Options.parse(Array(CommandLine.arguments.dropFirst()))
    let probe = SpaceMouseProbe(options: options)
    try probe.run()
} catch ProbeError.usage(let message) {
    fputs("error: \(message)\n\n", stderr)
    printHelp()
    exit(EXIT_FAILURE)
} catch {
    fputs("error: \(error)\n\n", stderr)
    exit(EXIT_FAILURE)
}
