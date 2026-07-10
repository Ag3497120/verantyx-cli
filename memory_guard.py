"""
memory_guard.py — メモリ消費の動的監視とロード制御 (OOMクラッシュ防止)
==============================================================================
- available_gb() / total_gb(): クロスプラットフォーム (macOS / Linux / Windows)
- MemoryGuard: モデルロード前の「入るか」判定と、圧迫時の自動アンロード勧告

方針:
  jgen は mmap なので RAM をほぼ食わない (ページキャッシュ任せ)。
  本当に危険なのは HF 直ロード (Ornith 9B ≈ 19GB) と GPU 重みキャッシュ。
  ロード前に「必要量 + 安全マージン」が空いていなければ、
  外部サーバー (Ollama / LM Studio) や下位モデルへ自動で切り替える。
"""

import os

try:
    import psutil
except ImportError:
    psutil = None

C_SYS = "\033[90m"
C_WARN = "\033[93m"
C_RST = "\033[0m"

# モデル別の実測ベース推定 RAM 使用量 (GB)
ESTIMATES = {
    "hf_sage_9b": 19.0,     # Ornith 9B bf16 (MPS/CPU)
    "jgen_worker": 4.0,     # mmap + 合成済み重みキャッシュ (JCROSS_CACHE_GB で上限)
    "jgen_router": 1.0,
    "lexicon": 0.5,         # mmap + ノルムキャッシュ
    "vision": 0.3,
}

SAFETY_MARGIN_GB = 3.0      # OS と他プロセスのための残し分
CRITICAL_GB = 2.0           # これを切ったら緊急アンロード勧告
TRIM_GB = 10.0              # これを切ったら非破壊トリム (重みキャッシュ解放) を実行


def total_gb():
    if psutil:
        return psutil.virtual_memory().total / 2**30
    return 16.0


def available_gb():
    """いま実際に使える RAM (GB)。macOS は inactive も回収可能として含まれる。"""
    if psutil:
        return psutil.virtual_memory().available / 2**30
    return 8.0


def pressure():
    """0.0 (余裕) 〜 1.0 (限界) のメモリ圧。"""
    if not psutil:
        return 0.5
    vm = psutil.virtual_memory()
    return 1.0 - vm.available / vm.total


class MemoryGuard:
    """ロード可否判定と圧迫時の対応を一元化する。"""

    def __init__(self, quiet=False):
        self.quiet = quiet
        self._unload_hooks = []  # (名前, 推定解放GB, callable)
        self._trim_hooks = {}    # 名前 -> callable (非破壊: キャッシュ解放のみ)

    def log(self, msg):
        if not self.quiet:
            print(msg)

    def register_unloadable(self, name, est_gb, unload_fn):
        """圧迫時にアンロードできる資源を登録する (大きい順に解放)。"""
        self._unload_hooks.append((name, est_gb, unload_fn))

    def unregister(self, name):
        self._unload_hooks = [h for h in self._unload_hooks if h[0] != name]

    def can_load(self, kind_or_gb, label=""):
        """kind 名 (ESTIMATES キー) または GB 数を受けてロード可否を返す。"""
        need = ESTIMATES.get(kind_or_gb, kind_or_gb if isinstance(kind_or_gb, (int, float)) else 2.0)
        avail = available_gb()
        ok = avail - need >= SAFETY_MARGIN_GB
        if not ok:
            self.log(f"{C_WARN}  [MemGuard] {label or kind_or_gb} のロードを拒否: "
                     f"必要 {need:.1f}GB + 余白 {SAFETY_MARGIN_GB:.0f}GB > 空き {avail:.1f}GB{C_RST}")
        return ok

    def ensure(self, kind_or_gb, label=""):
        """必要ならアンロードフックを大きい順に叩いて空きを作ってから可否を返す。"""
        if self.can_load(kind_or_gb, label):
            return True
        for name, est, fn in sorted(self._unload_hooks, key=lambda h: -h[1]):
            self.log(f"{C_WARN}  [MemGuard] 空き確保のため '{name}' (~{est:.0f}GB) をアンロード{C_RST}")
            try:
                fn()
            except Exception:
                pass
            self.unregister(name)
            if self.can_load(kind_or_gb, label):
                return True
        return self.can_load(kind_or_gb, label)

    def register_trimmable(self, name, trim_fn):
        """非破壊トリム (合成済み重みキャッシュの解放など) を登録する。
        アンロードと違いモデルは生きたままで、次の使用時に遅延再構成される。"""
        self._trim_hooks[name] = trim_fn

    def maybe_trim(self):
        """ターンの合間に呼ぶ。空きが TRIM_GB を切ったら全トリムフックを実行。"""
        avail = available_gb()
        if avail >= TRIM_GB or not self._trim_hooks:
            return False
        self.log(f"{C_WARN}  [MemGuard] 空きRAM {avail:.1f}GB — 重みキャッシュを解放"
                 f" ({', '.join(self._trim_hooks)}){C_RST}")
        for name, fn in list(self._trim_hooks.items()):
            try:
                fn()
            except Exception:
                pass
        import gc
        gc.collect()
        self.log(f"{C_SYS}  [MemGuard] トリム後: 空き {available_gb():.1f}GB{C_RST}")
        return True

    def check_critical(self):
        """生成の合間に呼ぶ。危険水域ならアンロードフックを実行して False を返す。"""
        avail = available_gb()
        if avail >= CRITICAL_GB:
            return True
        self.log(f"{C_WARN}  [MemGuard] 空きRAM {avail:.1f}GB — 危険水域。緊急アンロード実行{C_RST}")
        for name, est, fn in sorted(self._unload_hooks, key=lambda h: -h[1]):
            try:
                fn()
            except Exception:
                pass
        self._unload_hooks = []
        return False

    def status(self):
        vm_avail, vm_total = available_gb(), total_gb()
        bar_n = int((1 - vm_avail / vm_total) * 12)
        bar = "█" * bar_n + "░" * (12 - bar_n)
        return (f"RAM {vm_total - vm_avail:.1f}/{vm_total:.0f}GB 使用 {bar} "
                f"空き {vm_avail:.1f}GB")


GUARD = MemoryGuard()


if __name__ == "__main__":
    print(GUARD.status())
    print("hf_sage_9b ロード可:", GUARD.can_load("hf_sage_9b", "Ornith 9B"))
    print("jgen_worker ロード可:", GUARD.can_load("jgen_worker", "worker"))
