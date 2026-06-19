import Foundation
import Network
import CoreBluetooth
import VideoToolbox
import ARKit
import RealityKit
import QuartzCore

/// Phase 14: VisionOS Drop-in SDK (Client Side)
/// ユーザーが保有する「vision spatial tools」にドロップインで組み込める、
/// Mac(Verantyx)からのゼロコピー映像のデコードと、JCrossトラッキング情報の送信を行うコアモジュールです。
public class VisionClientCompositor: NSObject, CBCentralManagerDelegate {
    
    // --- Network.framework (P2P UDP) ---
    private var listenerConnection: NWConnection?
    private let targetPort: NWEndpoint.Port = 9090
    
    // --- VideoToolbox (Hardware Decoder) ---
    private var decompressionSession: VTDecompressionSession?
    private var videoFormatDescription: CMVideoFormatDescription?
    
    // --- CoreBluetooth (Discovery) ---
    private var centralManager: CBCentralManager?
    private let serviceUUID = CBUUID(string: "A1B2C3D4-1234-5678-90AB-CDEF12345678")
    
    // --- ARKit Tracking ---
    // (実際のvisionOSアプリでは ARKitSession と WorldTrackingProvider, HandTrackingProvider を使用します)
    
    public override init() {
        super.init()
        // BLEでの探索をスキップして直接接続する
        establishP2PConnection(to: "direct")
    }
    
    // MARK: - Discovery & Connection (AirDrop Style)
    private func setupBluetoothDiscovery() {
        centralManager = CBCentralManager(delegate: self, queue: nil)
    }
    
    public func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn {
            print("[VisionClient] Bluetooth Powered On. Scanning for Mac Host...")
            centralManager?.scanForPeripherals(withServices: [serviceUUID], options: nil)
        }
    }
    
    public func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String : Any], rssi RSSI: NSNumber) {
        print("[VisionClient] Discovered Mac Host! Initiating Wi-Fi 6 P2P (AWDL) Connection...")
        centralManager?.stopScan()
        
        // P2P UDP 接続の確立
        establishP2PConnection(to: peripheral.identifier.uuidString)
    }
    
    private func establishP2PConnection(to hostId: String) {
        let parameters = NWParameters.udp
        parameters.includePeerToPeer = true
        
        // ホスト名が verantyx-mac.local ではなくなっているため、実際のIPアドレスかホスト名を指定
        let endpoint = NWEndpoint.hostPort(host: "10.77.121.106", port: targetPort)
        listenerConnection = NWConnection(to: endpoint, using: parameters)
        
        listenerConnection?.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                print("[VisionClient] Connected to Mac via P2P UDP!")
                self?.startReceivingNALUnits()
                
                // トラッキング送信ループの開始（例: 90Hz または 250Hz）
                self?.startTrackingUploadLoop()
            case .failed(let error):
                print("[VisionClient] Connection failed: \(error)")
            default:
                break
            }
        }
        
        listenerConnection?.start(queue: .main)
    }
    
    // MARK: - NAL Unit Hardware Decoding
    
    private func startReceivingNALUnits() {
        listenerConnection?.receiveMessage { [weak self] (content, context, isComplete, error) in
            if let data = content {
                self?.decodeNALUnit(data)
            }
            if error == nil {
                self?.startReceivingNALUnits() // ループ
            }
        }
    }
    
    private func decodeNALUnit(_ data: Data) {
        // --- 概念実装: VTDecompressionSession への流し込み ---
        // 1. 受信した Data から CMBlockBuffer を生成
        // 2. SPS/PPSが届いた時点で CMVideoFormatDescriptionCreateFromH264ParameterSets を呼び出し
        // 3. VTDecompressionSessionCreate でセッションを構築
        // 4. 以降は VCL (実際のピクセルデータ) を VTDecompressionSessionDecodeFrame に流し込む
        // 5. コールバックで返ってきた CVPixelBuffer を RealityKit の VideoMaterial にマッピングして描画
    }
    
    // MARK: - JCross Pose Upload
    
    private func startTrackingUploadLoop() {
        // Timer等を使って高頻度で呼ばれる想定
        let timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 90.0, repeats: true) { [weak self] _ in
            self?.uploadJCrossPose()
        }
        RunLoop.main.add(timer, forMode: .common)
    }
    
    private func uploadJCrossPose() {
        // --- 概念実装: ARKit のアンカー情報から JCross を生成 ---
        // let headAnchor = worldTracking.queryDeviceAnchor(atTimestamp: CACurrentMediaTime())
        // let leftHand = handTracking.leftHandAnchor
        
        // 仮のデータを構築
        var payload = JCrossPayload(
            frameId: 0, // Mac側と同期するシーケンス
            timestamp: CACurrentMediaTime(),
            headNode: JCrossNode_VR(nodeId: 1),
            leftHandNode: JCrossNode_VR(nodeId: 2),
            rightHandNode: JCrossNode_VR(nodeId: 3),
            leftInput: JCrossZone_Input(parentNodeId: 2),
            rightInput: JCrossZone_Input(parentNodeId: 3)
        )
        
        // (ここで payload.headNode.position = headAnchor.transform 等をセット)
        
        let dataToSend = payload.serialize()
        listenerConnection?.send(content: dataToSend, completion: .contentProcessed({ error in
            if let error = error {
                print("[VisionClient] Failed to send JCross: \(error)")
            }
        }))
    }
}
