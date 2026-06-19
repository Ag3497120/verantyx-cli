#include <metal_stdlib>
using namespace metal;

/// 仮想マシンから送られてきた左目用と右目用のフレームを
/// Side-by-Side (SBS) 形式に合成するためのコンピュートシェーダー
kernel void stereo_compose_sbs(
    texture2d<half, access::read> leftEyeTexture [[texture(0)]],
    texture2d<half, access::read> rightEyeTexture [[texture(1)]],
    texture2d<half, access::write> outputTexture [[texture(2)]],
    uint2 gid [[thread_position_in_grid]]
) {
    uint width = outputTexture.get_width();
    uint height = outputTexture.get_height();

    // スレッド位置がテクスチャ範囲外なら終了
    if (gid.x >= width || gid.y >= height) {
        return;
    }

    uint halfWidth = width / 2;
    half4 color;

    // 左半分は左目テクスチャから、右半分は右目テクスチャからサンプリング
    if (gid.x < halfWidth) {
        // 左目: X座標を元の解像度にスケール
        uint2 srcPos = uint2(gid.x * 2, gid.y);
        color = leftEyeTexture.read(srcPos);
    } else {
        // 右目: X座標をオフセットしてスケール
        uint2 srcPos = uint2((gid.x - halfWidth) * 2, gid.y);
        color = rightEyeTexture.read(srcPos);
    }

    outputTexture.write(color, gid);
}
