# VR Bridge Guest OS (VM) Test Programs

このディレクトリには、Virtualization.framework によって立ち上げられたゲストOS（Linux/Windows）内部で実行するテスト用プログラムを格納します。

## 目的
ゲストOS上でゲームやSteamVRがレンダリングしたフレームバッファを、シリアライズ処理（コピー処理）を一切行わずにホストOS（macOS）に引き渡す「ゼロコピー（Zero-Copy）」の概念実証を行うためのテストクライアントです。

## `guest_writer.c`
Linuxゲスト向けのPoCライタープログラムです。

### ビルド方法 (Linux VM内)
```bash
gcc -O3 guest_writer.c -o guest_writer
```

### 実行方法
```bash
sudo ./guest_writer
```

### 動作概要
1. `/dev/zero` (実際の検証時は共有メモリのデバイスノード、例: `/dev/uio0`) を `mmap` でメモリにマッピングします。
2. マッピングした領域を前半（左目用）と後半（右目用）に分割します。
3. 60FPSのペースでダミーのカラーパターン（徐々に色が変化する）を直接メモリ空間に書き込みます。
4. このメモリは Mac 側の `HypervisorManager` および Metal シェーダーと物理的/仮想的に共有されているため、VM内でメモリに書き込んだ瞬間に、Mac側のエンコーダがそれを読み取れる状態になります。
