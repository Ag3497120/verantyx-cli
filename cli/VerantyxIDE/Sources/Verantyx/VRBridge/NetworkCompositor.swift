import Foundation
import Network
import CoreBluetooth

/// Phase 10: "AirDrop-style" P2P Low-Latency Protocol
/// Apple Vision Proとの間でWi-Fi 6 (AWDL / P2P) とBluetooth LEを用いた
/// 超低遅延・広帯域のカスタム通信リンクを確立します。
class NetworkCompositor: NSObject, CBPeripheralManagerDelegate {
    
    // --- Network.framework (UDP/TCP P2P) ---
    private var listener: NWListener?
    private var activeConnection: NWConnection?
    
    // --- CoreBluetooth (Discovery) ---
    private var peripheralManager: CBPeripheralManager?
    private let serviceUUID = CBUUID(string: "A1B2C3D4-1234-5678-90AB-CDEF12345678")
    
    override init() {
        super.init()
        setupBluetoothDiscovery()
        setupWiFiDirectListener()
    }
    
    // MARK: - Bluetooth LE Discovery (AirDrop Style)
    private func setupBluetoothDiscovery() {
        peripheralManager = CBPeripheralManager(delegate: self, queue: nil)
    }
    
    func peripheralManagerDidUpdateState(_ peripheral: CBPeripheralManager) {
        if peripheral.state == .poweredOn {
            print("[NetworkCompositor] Bluetooth Powered On. Starting BLE Advertising for Vision Pro...")
            let advertisementData: [String: Any] = [
                CBAdvertisementDataServiceUUIDsKey: [serviceUUID],
                CBAdvertisementDataLocalNameKey: "Verantyx-Host-Mac"
            ]
            peripheralManager?.startAdvertising(advertisementData)
        }
    }
    
    // MARK: - Wi-Fi 6 P2P (AWDL) UDP Listener
    private func setupWiFiDirectListener() {
        do {
            // UDPでカスタムプロトコルを構築
            let parameters = NWParameters.udp
            
            // AWDL (Apple Wireless Direct Link) を優先的に使用してルーターをバイパスする
            parameters.includePeerToPeer = true
            
            listener = try NWListener(using: parameters, on: 9090)
            
            listener?.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    print("[NetworkCompositor] P2P UDP Listener ready on port \(self.listener?.port?.rawValue ?? 0)")
                case .failed(let error):
                    print("[NetworkCompositor] P2P Listener failed: \(error)")
                default:
                    break
                }
            }
            
            listener?.newConnectionHandler = { [weak self] connection in
                print("[NetworkCompositor] Vision Pro Connected via P2P Link!")
                self?.activeConnection = connection
                self?.startReceivingTrackingData(on: connection)
                connection.start(queue: .main)
            }
            
            listener?.start(queue: .main)
            
        } catch {
            print("[NetworkCompositor] Failed to start listener: \(error)")
        }
    }
    
    // MARK: - Data Transmission
    
    /// VideoToolboxがエンコードした H.264/HEVC NALユニットを Vision Pro へ送信
    func sendEncodedVideoFrame(nalUnitData: Data, frameId: UInt32) {
        guard let connection = activeConnection, connection.state == .ready else { return }
        
        // --- 独自可逆圧縮 / ヘッダー付与 ---
        // 実際のコードでは、ここでフレームヘッダ（frameId, タイムスタンプ）を
        // 独自フォーマットでパックしてUDPパケットとして飛ばします。
        
        connection.send(content: nalUnitData, completion: .contentProcessed { error in
            if let error = error {
                print("[NetworkCompositor] Frame send error: \(error)")
            }
        })
    }
    
    /// Vision Pro からのトラッキング情報（頭・手の座標）を連続受信
    private func startReceivingTrackingData(on connection: NWConnection) {
        connection.receiveMessage { [weak self] (content, context, isComplete, error) in
            if let data = content {
                self?.decodeAndInjectTrackingData(data: data)
            }
            if error == nil {
                // ループして受信し続ける
                self?.startReceivingTrackingData(on: connection)
            }
        }
    }
    
    // --- Wine Tracking Integration ---
    private var wineTrackingConnection: NWConnection?
    
    private func setupWineTrackingConnection() {
        let endpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: 11001)
        wineTrackingConnection = NWConnection(to: endpoint, using: .udp)
        wineTrackingConnection?.stateUpdateHandler = { state in
            print("[NetworkCompositor] Wine Tracking UDP state: \(state)")
        }
        wineTrackingConnection?.start(queue: .main)
    }
    
    private func decodeAndInjectTrackingData(data: Data) {
        // --- Phase 11: 独自可逆圧縮 (Lossless) のデコード ---
        guard let payload = JCrossPayload.deserialize(from: data) else {
            print("[NetworkCompositor] Failed to decode JCrossPayload")
            return
        }
        
        // --- Phase 15: Half-Life Alyx 快適化 (JCross Pose Prediction) ---
        // 受信したネットワーク遅延（約2~3ms）と、エンコード・デコードに要する時間（約8~10ms）を考慮し、
        // 取得した頭・手の座標から「11ミリ秒後」の未来の位置を Extrapolation (外挿) します。
        let predictionTimeMs: Float = 11.0 / 1000.0 // 11ms
        
        var predictedHead = payload.headNode
        predictedHead.position.x += predictedHead.velocity.x * predictionTimeMs
        predictedHead.position.y += predictedHead.velocity.y * predictionTimeMs
        predictedHead.position.z += predictedHead.velocity.z * predictionTimeMs
        
        // （回転のクォータニオン予測もここに入ります）
        
        // デコード・予測した JCrossNode_VR と JCrossZone_Input のデータを
        // driver_verantyx.cpp が共有メモリ経由で読み取れる位置に書き込みます。
        // （これによりSteamVRには、ユーザーが11ms後に到達する「未来の座標」が渡されるため、
        //   表示される瞬間に物理的な頭の位置とピクセルが完全に一致し、酔いが激減します）
        
        // --- Phase X: Send to tb_streamer (Wine) via UDP ---
        sendTrackingToWine(predictedHead: predictedHead)
    }
    
    private func sendTrackingToWine(predictedHead: JCrossNode_VR) {
        if wineTrackingConnection == nil {
            setupWineTrackingConnection()
        }
        
        var packetData = Data()
        
        // Magic 0x504F5345 ("POSE")
        var magic: UInt32 = 0x504F5345
        packetData.append(Data(bytes: &magic, count: 4))
        
        // Convert Position and Rotation to 4x4 matrix for head
        var headMat = [Float](repeating: 0, count: 16)
        headMat[0] = 1.0; headMat[5] = 1.0; headMat[10] = 1.0; headMat[15] = 1.0
        headMat[12] = predictedHead.position.x
        headMat[13] = predictedHead.position.y
        headMat[14] = predictedHead.position.z
        
        for val in headMat {
            var f = val
            packetData.append(Data(bytes: &f, count: 4))
        }
        
        // Left hand (dummy/offset for now)
        var leftMat = [Float](repeating: 0, count: 16)
        leftMat[0] = 1.0; leftMat[5] = 1.0; leftMat[10] = 1.0; leftMat[15] = 1.0
        leftMat[12] = predictedHead.position.x - 0.2
        leftMat[13] = predictedHead.position.y - 0.2
        leftMat[14] = predictedHead.position.z - 0.3
        
        for val in leftMat {
            var f = val
            packetData.append(Data(bytes: &f, count: 4))
        }
        
        // Right hand (dummy/offset for now)
        var rightMat = [Float](repeating: 0, count: 16)
        rightMat[0] = 1.0; rightMat[5] = 1.0; rightMat[10] = 1.0; rightMat[15] = 1.0
        rightMat[12] = predictedHead.position.x + 0.2
        rightMat[13] = predictedHead.position.y - 0.2
        rightMat[14] = predictedHead.position.z - 0.3
        
        for val in rightMat {
            var f = val
            packetData.append(Data(bytes: &f, count: 4))
        }
        
        // Pinches
        var leftPinch: UInt8 = 0
        var rightPinch: UInt8 = 0
        packetData.append(Data(bytes: &leftPinch, count: 1))
        packetData.append(Data(bytes: &rightPinch, count: 1))
        
        wineTrackingConnection?.send(content: packetData, completion: .contentProcessed({ error in
            if let e = error {
                print("[NetworkCompositor] UDP tracking send error: \(e)")
            }
        }))
    }
}
