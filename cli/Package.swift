// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "VerantyxCLI",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "verantyx-cli", targets: ["VeraCLI"]),
        .library(name: "VeraCore", targets: ["VeraCore"]),
    ],
    dependencies: [
        // Add any external dependencies here later
    ],
    targets: [
        .target(
            name: "VeraCore",
            dependencies: [],
            path: "Sources/VeraCore"
        ),
        .executableTarget(
            name: "VeraCLI",
            dependencies: ["VeraCore"],
            path: "Sources/VeraCLI"
        )
    ]
)
