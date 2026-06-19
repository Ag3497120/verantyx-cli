import Foundation
import simd

/// Phase 11: JCross VR Protocol
/// AIの「空間記憶インデックス（jcross）」の概念をVRの 6DoF (6 Degrees of Freedom) に転用。
///
/// オリジナルの `jcross` の6軸 (Forward/Backward, Up/Down, Left/Right) は、
/// VR空間における3次元座標 (x, y, z) と、回転を表すクォータニオン (qx, qy, qz, qw) と数学的に同等です。
/// これにより、AIが解釈可能な空間ノード構造と、VRプレイヤーの物理的状態が完全に統合されます。

// MARK: - JCross 6-Axis VR Node

/// 空間内の一つの「ノード」（頭、左手、右手）を表現する構造体。
/// C言語（ドライバ側）の共有メモリと互換性を持たせるため、Cレイアウト互換（Packed）で定義します。
public struct JCrossNode_VR {
    // ノードID (頭=0x01, 左手=0x02, 右手=0x03 など)
    public var nodeId: UInt16
    
    // 状態フラグ (トラッキング有効/無効など)
    public var flags: UInt16
    
    // 空間座標 (X, Y, Z) - メートル単位
    public var position: simd_float3
    
    // 空間回転 (Quaternion: X, Y, Z, W)
    public var rotation: simd_quatf
    
    // 速度・加速度 (Prediction/Reprojection用)
    public var velocity: simd_float3
    public var angularVelocity: simd_float3
    
    public init(nodeId: UInt16) {
        self.nodeId = nodeId
        self.flags = 1
        self.position = simd_make_float3(0, 0, 0)
        self.rotation = simd_quaternion(0, 0, 0, 1)
        self.velocity = simd_make_float3(0, 0, 0)
        self.angularVelocity = simd_make_float3(0, 0, 0)
    }
}

// MARK: - JCross Zone Input (Controller State)

/// ノードに付随する「ゾーン（Zone）」情報を、VRコントローラーの入力状態として再定義。
public struct JCrossZone_Input {
    // どのノード（手）に対する入力か
    public var parentNodeId: UInt16
    
    // ボタンのビットマスク (A, B, X, Y, Menu, System など)
    public var buttonMask: UInt32
    
    // アナログトリガー (0.0 ~ 1.0)
    public var triggerValue: Float
    public var gripValue: Float
    
    // ジョイスティック / トラックパッド (X, Y)
    public var thumbstick: simd_float2
    
    public init(parentNodeId: UInt16) {
        self.parentNodeId = parentNodeId
        self.buttonMask = 0
        self.triggerValue = 0
        self.gripValue = 0
        self.thumbstick = simd_make_float2(0, 0)
    }
}

// MARK: - JCross Payload Frame

/// P2Pリンクに乗せて送受信される、可逆圧縮前提のパケットペイロード
public struct JCrossPayload {
    // フレーム/シーケンスID (順序保証と遅延計測用)
    public var frameId: UInt32
    
    // ホスト側の基準タイムスタンプ (ミリ秒)
    public var timestamp: Double
    
    // 各ノード（Head, Left Hand, Right Hand）
    public var headNode: JCrossNode_VR
    public var leftHandNode: JCrossNode_VR
    public var rightHandNode: JCrossNode_VR
    
    // 各ゾーン（コントローラー入力）
    public var leftInput: JCrossZone_Input
    public var rightInput: JCrossZone_Input
    
    /// バイナリへのシリアライズ (P2P通信用)
    public func serialize() -> Data {
        var copy = self
        return Data(bytes: &copy, count: MemoryLayout<JCrossPayload>.size)
    }
    
    /// バイナリからのデシリアライズ
    public static func deserialize(from data: Data) -> JCrossPayload? {
        guard data.count == MemoryLayout<JCrossPayload>.size else { return nil }
        return data.withUnsafeBytes { $0.load(as: JCrossPayload.self) }
    }
}
