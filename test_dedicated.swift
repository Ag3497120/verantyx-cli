import CompositorServices
import Metal

func test(drawable: LayerRenderer.Drawable) {
    for view in drawable.views {
        print(view)
    }
}
