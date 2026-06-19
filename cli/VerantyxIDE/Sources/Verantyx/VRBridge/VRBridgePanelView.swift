import SwiftUI
import Virtualization

struct VMViewRep: NSViewRepresentable {
    var virtualMachine: VZVirtualMachine?

    func makeNSView(context: Context) -> VZVirtualMachineView {
        let view = VZVirtualMachineView()
        view.capturesSystemKeys = true
        view.virtualMachine = virtualMachine
        return view
    }

    func updateNSView(_ nsView: VZVirtualMachineView, context: Context) {
        nsView.virtualMachine = virtualMachine
    }
}

/// VerantyxIDE 内に組み込まれた、VR Bridge (Zero-Copy) の制御・デバッグ用パネル
struct VRBridgePanelView: View {
    @ObservedObject private var hypervisor = HypervisorManager.shared
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Zero-Copy VR Bridge")
                    .font(.headline)
                
                Spacer()
                
                Button(action: {
                    if hypervisor.isRunning {
                        hypervisor.stopVM()
                    } else {
                        hypervisor.startVM()
                    }
                }) {
                    Text(hypervisor.isRunning ? "Stop VM" : "Start VM")
                        .foregroundColor(hypervisor.isRunning ? .red : .green)
                }
            }
            
            Divider()
            
            Text("Metal Stereo Compositor Pipeline")
                .font(.subheadline)
                .bold()
            
            if hypervisor.isRunning, let vm = hypervisor.virtualMachine {
                VMViewRep(virtualMachine: vm)
                    .frame(minHeight: 400)
                    .background(Color.black)
                    .cornerRadius(8)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.gray.opacity(0.3), lineWidth: 1))
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(hypervisor.logMessages, id: \.self) { msg in
                            Text(msg)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundColor(.gray)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 150)
                .padding()
                .background(Color.black.opacity(0.1))
                .cornerRadius(8)
            }
            
            Text("Note: This is a Proof of Concept (PoC) for the Zero-Copy memory transfer layer and Metal SBS video compositor.")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding()
        .frame(minWidth: 400)
    }
}
