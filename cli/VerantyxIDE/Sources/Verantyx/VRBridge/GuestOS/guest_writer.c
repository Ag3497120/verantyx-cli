#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <string.h>

// VR Bridge PoC: Guest OS Writer
// このプログラムは、LinuxゲストVM内で動作し、ホスト(Mac)と共有されたメモリ空間に
// 疑似的な「左目・右目」のフレームバッファデータ（カラーパターン）を直接書き込みます。

#define FRAME_WIDTH  1920
#define FRAME_HEIGHT 1080
#define BYTES_PER_PIXEL 4 // RGBA

// 左目用と右目用の2つのバッファ
#define FRAME_SIZE (FRAME_WIDTH * FRAME_HEIGHT * BYTES_PER_PIXEL)
#define TOTAL_MEMORY_SIZE (FRAME_SIZE * 2)

// ホストから割り当てられた仮想Pciデバイス（VirtIO Shared Memory等）のパス
// PoCではダミーとして /dev/zero や /dev/uio0 などを想定
#define SHARED_MEM_PATH "/dev/zero" // 実際の検証時は VirtIO のデバイスパスに変更

void generate_dummy_frame(uint8_t* buffer, uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < FRAME_SIZE; i += 4) {
        buffer[i]     = r; // R
        buffer[i + 1] = g; // G
        buffer[i + 2] = b; // B
        buffer[i + 3] = 255; // A
    }
}

int main(int argc, char** argv) {
    printf("[Guest OS] Starting VR Bridge Zero-Copy Writer...\n");

    int fd = open(SHARED_MEM_PATH, O_RDWR);
    if (fd < 0) {
        perror("Failed to open shared memory device");
        // テスト環境がない場合は、ローカルのダミーメモリでシミュレートして終了する
        printf("[Guest OS] Running in simulation mode (no actual shared device).\n");
    }

    // 共有メモリをマッピング (fdが無効な場合は無名マッピングでシミュレート)
    int map_flags = (fd >= 0) ? MAP_SHARED : (MAP_PRIVATE | MAP_ANONYMOUS);
    uint8_t* shared_memory = mmap(NULL, TOTAL_MEMORY_SIZE, PROT_READ | PROT_WRITE, map_flags, (fd >= 0) ? fd : -1, 0);

    if (shared_memory == MAP_FAILED) {
        perror("mmap failed");
        if (fd >= 0) close(fd);
        return 1;
    }

    uint8_t* left_eye_buffer = shared_memory;
    uint8_t* right_eye_buffer = shared_memory + FRAME_SIZE;

    printf("[Guest OS] Shared memory mapped at %p\n", shared_memory);

    // メインループ: 60FPSでダミーデータを書き込み続けるシミュレーション
    int frames = 0;
    while (frames < 300) { // 5秒間 (60fps * 5s = 300 frames)
        // アニメーション効果（色が徐々に変わる）
        uint8_t intensity = (frames % 255);

        // 左目は赤色ベース、右目は青色ベースのグラデーション
        generate_dummy_frame(left_eye_buffer, intensity, 0, 0);
        generate_dummy_frame(right_eye_buffer, 0, 0, intensity);

        // TODO: ここで VirtIO Socket などを使って、ホスト側に「書き込み完了」のシグナルを送る
        // 例: write(virtio_socket_fd, "FRAME_READY", 11);
        
        if (frames % 60 == 0) {
            printf("[Guest OS] Wrote frame %d to shared memory.\n", frames);
        }

        // ~16ms スリープ (60FPSシミュレーション)
        usleep(16666);
        frames++;
    }

    printf("[Guest OS] Finished writing %d frames.\n", frames);

    munmap(shared_memory, TOTAL_MEMORY_SIZE);
    if (fd >= 0) close(fd);

    return 0;
}
