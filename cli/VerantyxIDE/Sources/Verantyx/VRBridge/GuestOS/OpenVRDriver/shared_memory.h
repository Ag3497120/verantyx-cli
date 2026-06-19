// VR Bridge PoC: Shared Memory Structure for Windows Guest
#pragma once
#include <stdint.h>

// UMAゼロコピーパイプラインにおける、WindowsゲストからMacホストへ映像を引き渡すための構造体
// このメモリレイアウトは、Mac側の IOSurface (CVPixelBuffer) の生データ構造と完全に一致させる必要があります。

#define VRBRIDGE_FRAME_WIDTH 3840   // SBS: 1920x1080 * 2
#define VRBRIDGE_FRAME_HEIGHT 1080
#define VRBRIDGE_BYTES_PER_PIXEL 4  // RGBA8 (必要に応じて RGBA16Float 等に変更)

struct ZeroCopyFrameBuffer {
    // 同期用のヘッダー情報
    uint32_t frameId;
    uint32_t width;
    uint32_t height;
    uint32_t isReady; // 1 = Windows側が書き込み完了、Mac側でエンコード可能
    
    // トラッキング・タイムスタンプ情報
    double presentationTimeSeconds;
    
    // 生のピクセルバッファ (IOSurfaceと直結)
    // SteamVRの左目・右目のテクスチャをここにSide-by-Sideで書き込む
    uint8_t pixelData[VRBRIDGE_FRAME_WIDTH * VRBRIDGE_FRAME_HEIGHT * VRBRIDGE_BYTES_PER_PIXEL];
};

// --- TODO ---
// Windows側のVirtIO IVSHMEM (Inter-VM Shared Memory) デバイスドライバを介して
// 上記の構造体を物理メモリの特定アドレスにマッピングする。
