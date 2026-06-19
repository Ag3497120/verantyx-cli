// VR Bridge PoC: Verantyx Custom OpenVR Driver (Windows Guest)
// このドライバはSteamVRに対して「4K/90fpsの仮想VRヘッドセット」として振る舞い、
// レンダリングされたフレームバッファを横取りして Mac 側の Zero-Copy メモリに流し込みます。

#include <openvr_driver.h>
#include <windows.h>
#include <d3d11.h>
#include <iostream>
#include <thread>
#include <vector>
#include "shared_memory.h"

#pragma comment(lib, "d3d11.lib")

using namespace vr;

// --- 仮想ヘッドセット (HMD) デバイスクラス ---
class VerantyxHMD : public vr::ITrackedDeviceServerDriver, public vr::IVRDisplayComponent {
private:
    vr::TrackedDeviceIndex_t m_unObjectId;
    vr::PropertyContainerHandle_t m_ulPropertyContainer;
    
    // VirtioFS 経由で Mac 側の IOSurface と直結するポインタ
    ZeroCopyFrameBuffer* m_pSharedFrameBuffer;
    HANDLE m_hMapFile;
    HANDLE m_hFile;

    // --- Phase 8: DirectX 11 Resources ---
    ID3D11Device* m_pDevice;
    ID3D11DeviceContext* m_pContext;
    ID3D11Texture2D* m_pStagingTexture;
    bool m_bD3D11Initialized;

public:
    VerantyxHMD() {
        m_unObjectId = vr::k_unTrackedDeviceIndexInvalid;
        m_ulPropertyContainer = vr::k_ulInvalidPropertyContainer;
        m_pSharedFrameBuffer = nullptr;
        m_hMapFile = NULL;
        m_hFile = INVALID_HANDLE_VALUE;
        
        m_pDevice = nullptr;
        m_pContext = nullptr;
        m_pStagingTexture = nullptr;
        m_bD3D11Initialized = false;
    }

    virtual ~VerantyxHMD() {}

    // --- ITrackedDeviceServerDriver 実装 ---
    virtual EVRInitError Activate(uint32_t unObjectId) override {
        m_unObjectId = unObjectId;
        m_ulPropertyContainer = vr::VRProperties()->TrackedDeviceToPropertyContainer(m_unObjectId);

        // HMDとしての基本プロパティをSteamVRに宣言
        vr::VRProperties()->SetStringProperty(m_ulPropertyContainer, Prop_ModelNumber_String, "Verantyx Zero-Copy HMD");
        vr::VRProperties()->SetStringProperty(m_ulPropertyContainer, Prop_SerialNumber_String, "VRNTX-001");
        vr::VRProperties()->SetFloatProperty(m_ulPropertyContainer, Prop_UserIpdMeters_Float, 0.063f);
        vr::VRProperties()->SetFloatProperty(m_ulPropertyContainer, Prop_DisplayFrequency_Float, 90.0f);

        // --- Phase 7: The "VirtioFS mmap" Zero-Copy Hack ---
        // VirtioFS でマウントされた Mac 側の共有フォルダ内のダミーファイルを開く
        // Mac側はこれを mmap して IOSurface とリンクさせる
        m_hFile = CreateFileA("Z:\\vr_framebuffer.bin",
                              GENERIC_READ | GENERIC_WRITE,
                              FILE_SHARE_READ | FILE_SHARE_WRITE,
                              NULL,
                              OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL,
                              NULL);

        if (m_hFile != INVALID_HANDLE_VALUE) {
            m_hMapFile = CreateFileMapping(m_hFile, NULL, PAGE_READWRITE, 0, sizeof(ZeroCopyFrameBuffer), NULL);
            if (m_hMapFile != NULL) {
                m_pSharedFrameBuffer = (ZeroCopyFrameBuffer*)MapViewOfFile(m_hMapFile, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(ZeroCopyFrameBuffer));
            }
        }
        // ----------------------------------------------------

        return VRInitError_None;
    }

    virtual void Deactivate() override {
        m_unObjectId = vr::k_unTrackedDeviceIndexInvalid;
        
        // D3D11 クリーンアップ
        if (m_pStagingTexture) { m_pStagingTexture->Release(); m_pStagingTexture = nullptr; }
        if (m_pContext) { m_pContext->Release(); m_pContext = nullptr; }
        if (m_pDevice) { m_pDevice->Release(); m_pDevice = nullptr; }
        
        if (m_pSharedFrameBuffer) {
            UnmapViewOfFile(m_pSharedFrameBuffer);
            m_pSharedFrameBuffer = nullptr;
        }
        if (m_hMapFile) {
            CloseHandle(m_hMapFile);
            m_hMapFile = NULL;
        }
        if (m_hFile != INVALID_HANDLE_VALUE) {
            CloseHandle(m_hFile);
            m_hFile = INVALID_HANDLE_VALUE;
        }
    }

    virtual void EnterStandby() override {}
    virtual void* GetComponent(const char* pchComponentNameAndVersion) override {
        if (!_stricmp(pchComponentNameAndVersion, vr::IVRDisplayComponent_Version)) {
            return (vr::IVRDisplayComponent*)this;
        }
        return nullptr;
    }
    virtual void DebugRequest(const char* pchRequest, char* pchResponseBuffer, uint32_t unResponseBufferSize) override {}
    virtual DriverPose_t GetPose() override {
        // TODO: Mac側 (Vision Pro) から送られてきた最新のトラッキング座標を返す
        DriverPose_t pose = {0};
        pose.poseIsValid = true;
        pose.result = TrackingResult_Running_OK;
        pose.deviceIsConnected = true;
        pose.qRotation.w = 1; pose.qRotation.x = 0; pose.qRotation.y = 0; pose.qRotation.z = 0;
        pose.vecPosition[0] = 0; pose.vecPosition[1] = 1.5; pose.vecPosition[2] = 0; // 身長約1.5m
        return pose;
    }

    // --- IVRDisplayComponent 実装 ---
    virtual void GetWindowBounds(int32_t* pnX, int32_t* pnY, uint32_t* pnWidth, uint32_t* pnHeight) override {
        *pnX = 0;
        *pnY = 0;
        *pnWidth = 3840; // 1920 * 2 (SBS)
        *pnHeight = 1080;
    }
    virtual bool IsDisplayOnDesktop() override { return false; }
    virtual bool IsDisplayRealDisplay() override { return false; }
    virtual void GetRecommendedRenderTargetSize(uint32_t* pnWidth, uint32_t* pnHeight) override {
        *pnWidth = 1920; // 片目
        *pnHeight = 1080;
    }
    virtual void GetEyeOutputViewport(EVREye eEye, uint32_t* pnX, uint32_t* pnY, uint32_t* pnWidth, uint32_t* pnHeight) override {
        *pnY = 0;
        *pnWidth = 1920;
        *pnHeight = 1080;
        *pnX = (eEye == Eye_Left) ? 0 : 1920;
    }
    virtual void GetProjectionRaw(EVREye eEye, float* pfLeft, float* pfRight, float* pfTop, float* pfBottom) override {
        *pfLeft = -1.0f; *pfRight = 1.0f; *pfTop = -1.0f; *pfBottom = 1.0f;
    }
    virtual DistortionCoordinates_t ComputeDistortion(EVREye eEye, float fU, float fV) override {
        // ディストーション（歪み補正）は Mac 側の Metal (StereoCompositor.metal) に任せるため、ここではスルー
        DistortionCoordinates_t coords;
        coords.rfBlue[0] = fU; coords.rfBlue[1] = fV;
        coords.rfGreen[0] = fU; coords.rfGreen[1] = fV;
        coords.rfRed[0] = fU; coords.rfRed[1] = fV;
        return coords;
    }

    // ★ 核心部: SteamVRがフレームを描画し終えた瞬間に呼ばれる
    virtual void SubmitLayer(const vr::VRTextureBounds_t* pBounds, vr::EVREye eEye, vr::Texture_t* pTexture) override {
        if (!m_pSharedFrameBuffer || pTexture->eType != vr::TextureType_DirectX) return;

        ID3D11Texture2D* pSrcTexture = (ID3D11Texture2D*)pTexture->handle;

        // 遅延初期化: 初回の SubmitLayer で D3D11 デバイスと Staging テクスチャをセットアップ
        if (!m_bD3D11Initialized) {
            D3D11_TEXTURE2D_DESC srcDesc;
            pSrcTexture->GetDesc(&srcDesc);

            // Staging テクスチャの作成 (CPUから読み取り可能にするため)
            D3D11_TEXTURE2D_DESC stagingDesc = srcDesc;
            stagingDesc.Usage = D3D11_USAGE_STAGING;
            stagingDesc.BindFlags = 0;
            stagingDesc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
            stagingDesc.MiscFlags = 0;

            pSrcTexture->GetDevice(&m_pDevice);
            m_pDevice->GetImmediateContext(&m_pContext);
            m_pDevice->CreateTexture2D(&stagingDesc, nullptr, &m_pStagingTexture);
            m_bD3D11Initialized = true;
        }

        if (!m_pStagingTexture) return;

        // GPUからStagingテクスチャへDMA転送（非同期コピー）
        m_pContext->CopyResource(m_pStagingTexture, pSrcTexture);

        // CPUメモリ空間へマップし、DAX共有メモリ（VirtioFS）へBlit
        D3D11_MAPPED_SUBRESOURCE mapped;
        if (SUCCEEDED(m_pContext->Map(m_pStagingTexture, 0, D3D11_MAP_READ, 0, &mapped))) {
            
            // ピクセルフォーマット（通常は RGBA8）に従い、左右の目に分割してコピー
            uint32_t width = 1920;
            uint32_t height = 1080;
            uint32_t bytesPerPixel = 4;
            uint32_t srcRowPitch = mapped.RowPitch;
            uint32_t dstRowPitch = 3840 * bytesPerPixel; // 1920 * 2
            
            uint8_t* pDst = m_pSharedFrameBuffer->pixelData;
            uint8_t* pSrc = (uint8_t*)mapped.pData;
            
            // 右目の場合はオフセットをずらす
            if (eEye == vr::Eye_Right) {
                pDst += (1920 * bytesPerPixel);
            }

            // 行ごとにコピー (memcpy による高速コピー)
            // --- Phase 15: Half-Life Alyx 快適化 (並列コピーチューニング) ---
            // 4K映像の 8MB をシングルスレッドでコピーすると CPU キャッシュを圧迫して数ミリ秒の遅延を生むため、
            // 4スレッドに分割して AVX レベルで並列 DMA を叩き込む。
            const uint32_t numThreads = 4;
            std::vector<std::thread> threads;
            uint32_t rowsPerThread = height / numThreads;

            for (uint32_t t = 0; t < numThreads; ++t) {
                threads.emplace_back([=]() {
                    uint32_t startY = t * rowsPerThread;
                    uint32_t endY = (t == numThreads - 1) ? height : startY + rowsPerThread;
                    for (uint32_t y = startY; y < endY; ++y) {
                        memcpy(pDst + (y * dstRowPitch), pSrc + (y * srcRowPitch), width * bytesPerPixel);
                    }
                });
            }
            
            for (auto& thread : threads) {
                thread.join();
            }
            // -------------------------------------------------------------

            m_pContext->Unmap(m_pStagingTexture, 0);
        }
        
        // 最後に Mac 側に「フレーム完成」のシグナルを送る
        if (eEye == vr::Eye_Right) {
            m_pSharedFrameBuffer->isReady = 1;
            m_pSharedFrameBuffer->frameId++;
        }
    }
};

// --- プロバイダークラス ---
class VerantyxServerDriver : public vr::IServerTrackedDeviceProvider {
private:
    VerantyxHMD* m_pHMD = nullptr;

public:
    virtual EVRInitError Init(vr::IVRDriverContext* pDriverContext) override {
        VR_INIT_SERVER_DRIVER_CONTEXT(pDriverContext);
        m_pHMD = new VerantyxHMD();
        vr::VRServerDriverHost()->TrackedDeviceAdded(m_pHMD->GetSerialNumber(), vr::TrackedDeviceClass_HMD, m_pHMD);
        return VRInitError_None;
    }
    virtual void Cleanup() override {
        delete m_pHMD;
        m_pHMD = nullptr;
    }
    virtual const char* const* GetInterfaceVersions() override {
        return vr::k_InterfaceVersions;
    }
    virtual void RunFrame() override {
        if (m_pHMD) {
            vr::VRServerDriverHost()->TrackedDevicePoseUpdated(m_pHMD->GetObjectId(), m_pHMD->GetPose(), sizeof(DriverPose_t));
        }
    }
    virtual bool ShouldBlockStandbyMode() override { return false; }
    virtual void EnterStandby() override {}
    virtual void LeaveStandby() override {}
};

VerantyxServerDriver g_serverDriverNull;

// --- エントリポイント (SteamVR が DLL をロードする際に呼ばれる) ---
#if defined(_WIN32)
#define HMD_DLL_EXPORT extern "C" __declspec( dllexport )
#endif

HMD_DLL_EXPORT void* HmdDriverFactory(const char* pInterfaceName, int* pReturnCode) {
    if (0 == strcmp(IServerTrackedDeviceProvider_Version, pInterfaceName)) {
        return &g_serverDriverNull;
    }
    if (pReturnCode) *pReturnCode = VRInitError_Init_InterfaceNotFound;
    return NULL;
}
