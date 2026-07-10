import CompositorServices
import ARKit
import QuartzCore

func test(drawable: LayerRenderer.Drawable, provider: WorldTrackingProvider) {
    if let anchor = provider.queryDeviceAnchor(atTimestamp: CACurrentMediaTime()) {
        drawable.deviceAnchor = anchor
    }
}
