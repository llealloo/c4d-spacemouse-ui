// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "SpaceMouseProbe",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "spacemouse-probe", targets: ["SpaceMouseProbe"])
    ],
    targets: [
        .executableTarget(
            name: "SpaceMouseProbe",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("IOKit")
            ]
        )
    ]
)
