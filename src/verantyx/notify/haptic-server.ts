import { createServer, type Server, type Socket } from "net";
import { EventEmitter } from "events";

// MARK: - Verantyx Haptic Notification Server
//
// Mac側のサーバー。ローカルネットワークでiPhone Companion Appと通信。
// イベント発生時に振動パターンを送信し、背面タップによる返信を受信。

export type HapticPattern = "error" | "message" | "approval" | "complete" | "morse";
export type TapReply = "yes" | "no" | "hold" | "custom1" | "custom2";

export interface HapticEvent {
  type: HapticPattern;
  message: string;
  timestamp: number;
  requiresReply: boolean;
  morseText?: string; // モールス信号モード用
}

export interface TapReplyEvent {
  tapCount: number;
  reply: TapReply;
  timestamp: number;
}

// 振動パターン定義
export const HAPTIC_PATTERNS: Record<HapticPattern, number[]> = {
  error:    [100, 100, 100, 100, 100, 100, 100, 100, 100], // 5回短振動
  message:  [100, 100, 100, 100, 100],                      // 3回短振動
  approval: [100, 100, 100],                                  // 2回短振動
  complete: [400],                                            // 1回長振動
  morse:    [],                                               // 動的生成
};

// タップ回数 → 返信マッピング
export const TAP_REPLIES: Record<number, TapReply> = {
  1: "yes",
  2: "no",
  3: "hold",
  4: "custom1",
  5: "custom2",
};

// カスタム返信のデフォルト内容
export const DEFAULT_CUSTOM_REPLIES: Record<string, string> = {
  yes: "Approved / Yes",
  no: "Rejected / No",
  hold: "Hold / Later",
  custom1: "Continue without me",
  custom2: "Stop and wait",
};

// モールス信号マッピング
const MORSE_CODE: Record<string, string> = {
  "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".",
  "f": "..-.", "g": "--.", "h": "....", "i": "..", "j": ".---",
  "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---",
  "p": ".--.", "q": "--.-", "r": ".-.", "s": "...", "t": "-",
  "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--",
  "z": "--..", "0": "-----", "1": ".----", "2": "..---",
  "3": "...--", "4": "....-", "5": ".....", "6": "-....",
  "7": "--...", "8": "---..", "9": "----.",
  " ": " ",
};

export function textToMorse(text: string): number[] {
  const pattern: number[] = [];
  const DOT = 80;
  const DASH = 250;
  const SYMBOL_GAP = 80;
  const LETTER_GAP = 200;
  const WORD_GAP = 500;

  for (const char of text.toLowerCase()) {
    if (char === " ") {
      pattern.push(WORD_GAP);
      continue;
    }
    const morse = MORSE_CODE[char];
    if (!morse) {continue;}

    for (let i = 0; i < morse.length; i++) {
      if (morse[i] === ".") {pattern.push(DOT);}
      else if (morse[i] === "-") {pattern.push(DASH);}
      if (i < morse.length - 1) {pattern.push(SYMBOL_GAP);}
    }
    pattern.push(LETTER_GAP);
  }
  return pattern;
}

export class HapticServer extends EventEmitter {
  private server: Server | null = null;
  private clients: Set<Socket> = new Set();
  private port: number;
  private pendingApproval: ((reply: TapReply) => void) | null = null;
  private customReplies: Record<string, string>;

  constructor(port = 19800) {
    super();
    this.port = port;
    this.customReplies = { ...DEFAULT_CUSTOM_REPLIES };
  }

  // サーバー起動
  start(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.server = createServer((socket) => {
        this.clients.add(socket);
        console.log(`[haptic] 📱 Device connected (${this.clients.size} active)`);

        socket.on("data", (data) => {
          try {
            const msg = JSON.parse(data.toString().trim());
            this.handleClientMessage(msg);
          } catch { /* ignore malformed */ }
        });

        socket.on("close", () => {
          this.clients.delete(socket);
          console.log(`[haptic] 📱 Device disconnected (${this.clients.size} active)`);
        });

        socket.on("error", () => {
          this.clients.delete(socket);
        });

        // 接続確認を送信
        this.sendToSocket(socket, {
          type: "connected",
          customReplies: this.customReplies,
          timestamp: Date.now(),
        });
      });

      this.server.listen(this.port, "0.0.0.0", () => {
        console.log(`[haptic] 🔔 Haptic server listening on port ${this.port}`);
        resolve();
      });

      this.server.on("error", (err) => {
        if ((err as any).code === "EADDRINUSE") {
          console.log(`[haptic] ⚠ Port ${this.port} in use, trying ${this.port + 1}`);
          this.port++;
          this.server?.listen(this.port, "0.0.0.0");
        } else {
          reject(err);
        }
      });
    });
  }

  // サーバー停止
  stop(): void {
    for (const client of this.clients) {
      client.destroy();
    }
    this.clients.clear();
    this.server?.close();
    this.server = null;
  }

  // 接続中のデバイス数
  get connectedDevices(): number {
    return this.clients.size;
  }

  // 振動パターンを送信
  sendHaptic(event: HapticEvent): void {
    let pattern: number[];

    if (event.type === "morse" && event.morseText) {
      pattern = textToMorse(event.morseText);
    } else {
      pattern = HAPTIC_PATTERNS[event.type];
    }

    const payload = {
      type: "haptic",
      pattern,
      hapticType: event.type,
      message: event.message,
      requiresReply: event.requiresReply,
      timestamp: event.timestamp,
    };

    this.broadcast(payload);
  }

  // エラー通知（5回振動）
  notifyError(message: string): void {
    this.sendHaptic({
      type: "error",
      message,
      timestamp: Date.now(),
      requiresReply: false,
    });
  }

  // メッセージ受信通知（3回振動）
  notifyMessage(message: string): void {
    this.sendHaptic({
      type: "message",
      message: message.substring(0, 200), // 先頭200文字
      timestamp: Date.now(),
      requiresReply: false,
    });
  }

  // 承認要求（2回振動 + 返信待ち）
  async requestApproval(message: string, timeoutMs = 60000): Promise<TapReply> {
    this.sendHaptic({
      type: "approval",
      message,
      timestamp: Date.now(),
      requiresReply: true,
    });

    return new Promise<TapReply>((resolve) => {
      const timer = setTimeout(() => {
        this.pendingApproval = null;
        resolve("hold"); // タイムアウト → 保留
      }, timeoutMs);

      this.pendingApproval = (reply) => {
        clearTimeout(timer);
        this.pendingApproval = null;
        resolve(reply);
      };
    });
  }

  // タスク完了通知（1回長振動）
  notifyComplete(message: string): void {
    this.sendHaptic({
      type: "complete",
      message,
      timestamp: Date.now(),
      requiresReply: false,
    });
  }

  // モールス信号通知
  notifyMorse(text: string): void {
    this.sendHaptic({
      type: "morse",
      message: text,
      morseText: text,
      timestamp: Date.now(),
      requiresReply: false,
    });
  }

  // カスタム返信内容を設定
  setCustomReply(key: string, value: string): void {
    this.customReplies[key] = value;
    // 接続中のデバイスに更新を通知
    this.broadcast({
      type: "config_update",
      customReplies: this.customReplies,
      timestamp: Date.now(),
    });
  }

  // クライアントからのメッセージ処理
  private handleClientMessage(msg: any): void {
    if (msg.type === "tap_reply") {
      const tapCount = msg.tapCount as number;
      const reply = TAP_REPLIES[tapCount] || "hold";

      console.log(`[haptic] 👆 Tap reply: ${tapCount}x → ${reply} (${this.customReplies[reply]})`);

      // 確認振動を送信（タップ数と同じ回数）
      const confirmPattern = Array.from({ length: tapCount * 2 - 1 }, (_, i) =>
        i % 2 === 0 ? 150 : 100
      );
      this.broadcast({
        type: "confirm",
        pattern: confirmPattern,
        reply,
        replyText: this.customReplies[reply],
        timestamp: Date.now(),
      });

      // 承認待ちがあれば解決
      if (this.pendingApproval) {
        this.pendingApproval(reply);
      }

      this.emit("reply", { tapCount, reply, timestamp: Date.now() } as TapReplyEvent);
    }

    if (msg.type === "cancel") {
      console.log(`[haptic] ✋ Reply cancelled by user`);
      if (this.pendingApproval) {
        this.pendingApproval("hold");
      }
    }
  }

  // 全クライアントにブロードキャスト
  private broadcast(payload: any): void {
    const data = JSON.stringify(payload) + "\n";
    for (const client of this.clients) {
      try {
        client.write(data);
      } catch { /* ignore dead sockets */ }
    }
  }

  // 特定ソケットに送信
  private sendToSocket(socket: Socket, payload: any): void {
    try {
      socket.write(JSON.stringify(payload) + "\n");
    } catch { /* ignore */ }
  }
}
