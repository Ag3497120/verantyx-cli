#!/bin/bash
# VR Bridge PoC: Windows ARM Unattended Provisioning Script
#
# Usage: ./setup_vm.sh <path_to_windows_arm_insider_vhdx>
#
# このスクリプトは、Virtualization.framework で動かすためのWindows環境を全自動で構築します。

set -e

VHDX_PATH=$1
VM_DIR="/tmp/VerantyxVM"
IMG_PATH="$VM_DIR/windows.img"
ISO_PATH="$VM_DIR/unattend.iso"

if [ -z "$VHDX_PATH" ]; then
    echo "Usage: $0 <path_to_vhdx>"
    exit 1
fi

echo "=> [1/4] VMディレクトリの作成: $VM_DIR"
mkdir -p "$VM_DIR"

# qemu-img を使用してVHDXをRAW (IMG) に変換 (Homebrewのqemuが必要)
echo "=> [2/4] VHDX を Virtualization.framework 用の RAW img に変換しています..."
if ! command -v qemu-img &> /dev/null; then
    echo "エラー: qemu-img が見つかりません。 'brew install qemu' を実行してください。"
    exit 1
fi
qemu-img convert -f vhdx -O raw "$VHDX_PATH" "$IMG_PATH"

echo "=> [3/4] AutoUnattend.xml を含む仮想CD-ROM (ISO) を生成しています..."
# macOS 標準の hdiutil を使用してISOイメージを作成
hdiutil makehybrid -iso -joliet -o "$ISO_PATH" ./AutoUnattend.xml

echo "=> [4/4] 準備完了！"
echo "VM イメージ: $IMG_PATH"
echo "Unattend ISO: $ISO_PATH"
echo ""
echo "これで HypervisorManager.swift からこのディスクをマウントして起動すれば、"
echo "完全に無人でSSHサーバが立ち上がり、ドライバが同期される状態になります。"
