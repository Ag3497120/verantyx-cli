"""
vision_memory.py — 永遠の記憶の視覚層 (立体十字構造体式データ削減)
==============================================================================
スクリーンショットを「立体十字」流の多重解像度ノードに圧縮して永続化する。
5MB の生画像を、検索に使う部分は 4KB 台まで削る:

  L1   : 8次元のグローバル署名 (明度/彩度/色相/エッジ密度/テキスト密度/コントラスト...)
  L1.5 : 1024次元の格子埋め込み (16x16 セル x [輝度, R-G, B-Y, エッジ] = 視覚指紋)
  L2   : OCR で読んだ画面上の語 (概念列)
  L3   : 生の真実 = 縮小 JPEG のパス + OCR 全文 (座標つき)

OCR は macOS 内蔵 Vision フレームワーク (pyobjc) を使うため、
モデルのロードは一切不要 = メモリゼロで「画像認識」できる。
座標つきの読み取りができるので、正確なコンピュータ操作 (テキストを
見つけてクリック) の土台になる。
"""

import json
import os
import subprocess
import time

import numpy as np

VISION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono")
VISION_VEC = os.path.join(VISION_DIR, "vision.vectors")
VISION_IDX = os.path.join(VISION_DIR, "vision.index.jsonl")
SHOT_DIR = os.path.join(VISION_DIR, "shots")
GRID = 16          # 16x16 セル
FEAT = 4           # セルあたり特徴数 -> 16*16*4 = 1024 次元
DIM = GRID * GRID * FEAT


# ── スクリーンショット取得 ────────────────────────────────────────────────────
def take_screenshot(path=None):
    path = path or f"/tmp/vx_screen_{int(time.time())}.png"
    subprocess.run(["screencapture", "-x", path], check=True, timeout=15)
    return path


# ── OCR (macOS Vision framework / モデルロード不要) ──────────────────────────
def ocr_image(png_path, langs=("ja", "en")):
    """[(text, cx, cy, w, h), ...] を画像ピクセル座標で返す。"""
    import Quartz
    import Vision
    url = Quartz.CFURLCreateFromFileSystemRepresentation(
        None, png_path.encode(), len(png_path.encode()), False)
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    if src is None:
        return [], (0, 0)
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    iw, ih = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)

    results = []

    def handler(request, error):
        for obs in request.results() or []:
            cand = obs.topCandidates_(1)
            if not cand:
                continue
            text = cand[0].string()
            bb = obs.boundingBox()  # 正規化座標 (原点は左下)
            cx = (bb.origin.x + bb.size.width / 2) * iw
            cy = (1.0 - bb.origin.y - bb.size.height / 2) * ih
            results.append((str(text), float(cx), float(cy),
                            float(bb.size.width * iw), float(bb.size.height * ih)))

    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    try:
        request.setRecognitionLanguages_(["ja-JP", "en-US"])
    except Exception:
        pass
    hdl = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
    hdl.performRequests_error_([request], None)
    return results, (iw, ih)


# ── 立体十字式圧縮 ────────────────────────────────────────────────────────────
def _load_gray_rgb(png_path, size=256):
    from PIL import Image
    im = Image.open(png_path).convert("RGB").resize((size, size))
    rgb = np.asarray(im, dtype=np.float32) / 255.0
    gray = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return gray, rgb


def grid_embedding(png_path):
    """1024 次元の視覚指紋 (L1.5)。16x16 セル x [輝度, R-G, B-Y, エッジ]。"""
    gray, rgb = _load_gray_rgb(png_path)
    size = gray.shape[0]
    cell = size // GRID
    # Sobel近似エッジ
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    edge = gx + gy
    feats = np.zeros((GRID, GRID, FEAT), dtype=np.float32)
    for i in range(GRID):
        for j in range(GRID):
            ys, xs = slice(i * cell, (i + 1) * cell), slice(j * cell, (j + 1) * cell)
            block, eb = rgb[ys, xs], edge[ys, xs]
            feats[i, j, 0] = gray[ys, xs].mean()
            feats[i, j, 1] = (block[..., 0] - block[..., 1]).mean()  # R-G 対立色
            feats[i, j, 2] = (block[..., 2] - block[..., :2].mean(axis=-1)).mean()  # B-Y
            feats[i, j, 3] = eb.mean()
    v = feats.reshape(-1)
    return v / (np.linalg.norm(v) + 1e-8)


def global_signature(png_path, ocr_items):
    """8次元の L1 署名。"""
    gray, rgb = _load_gray_rgb(png_path, size=128)
    sat = rgb.max(axis=-1) - rgb.min(axis=-1)
    gx = np.abs(np.diff(gray, axis=1)).mean()
    gy = np.abs(np.diff(gray, axis=0)).mean()
    text_density = min(len(ocr_items) / 80.0, 1.0)
    return [round(float(x), 4) for x in (
        gray.mean(), gray.std(), sat.mean(),
        rgb[..., 0].mean(), rgb[..., 2].mean(),
        gx + gy, text_density, len(ocr_items))]


# ── 視覚層本体 ────────────────────────────────────────────────────────────────
class VisionMemory:
    def __init__(self):
        os.makedirs(SHOT_DIR, exist_ok=True)
        self.index = []
        if os.path.exists(VISION_IDX):
            with open(VISION_IDX) as f:
                self.index = [json.loads(l) for l in f if l.strip()]
        self._vecs = None

    def _vectors(self):
        if self._vecs is None and os.path.exists(VISION_VEC):
            self._vecs = np.fromfile(VISION_VEC, dtype=np.float32).reshape(-1, DIM)
        return self._vecs if self._vecs is not None else np.zeros((0, DIM), dtype=np.float32)

    def imprint_screen(self, png_path=None, label=""):
        """画面を1枚、視覚層に刻印して node dict を返す。"""
        own_shot = png_path is None
        if own_shot:
            png_path = take_screenshot()
        ocr_items, (iw, ih) = ocr_image(png_path)
        emb = grid_embedding(png_path)
        sig = global_signature(png_path, ocr_items)

        # L3: 縮小 JPEG (~100KB) として保存し、元の巨大 PNG は捨てられる
        nid = len(self.index)
        jpg = os.path.join(SHOT_DIR, f"shot_{nid:05d}.jpg")
        from PIL import Image
        im = Image.open(png_path)
        im.convert("RGB").resize((im.width // 2, im.height // 2)).save(jpg, quality=60)
        if own_shot:
            os.unlink(png_path)

        words = [t for t, *_ in ocr_items]
        node = {
            "id": nid, "ts": time.time(), "label": label,
            "L1_signature": sig,
            "L2_concepts": _top_words(words, 12),
            "L3_jpeg": jpg,
            "L3_ocr": [[t, round(x, 1), round(y, 1), round(w, 1), round(h, 1)]
                       for t, x, y, w, h in ocr_items],
            "screen_px": [iw, ih],
        }
        with open(VISION_IDX, "a") as f:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")
        with open(VISION_VEC, "ab") as f:
            emb.astype(np.float32).tofile(f)
        self.index.append(node)
        self._vecs = None
        return node

    def search_visual(self, png_path, k=3):
        """いまの画面に「見た目が」近い過去画面 (L1.5 コサイン)。"""
        if not self.index:
            return []
        q = grid_embedding(png_path)
        V = self._vectors()
        sims = V @ q
        order = np.argsort(sims)[::-1][:k]
        return [(self.index[i], float(sims[i])) for i in order]

    def search_text(self, query, k=3):
        """OCR 済みテキスト (L2/L3) に対する語検索。"""
        ql = query.lower()
        scored = []
        for node in self.index:
            text = " ".join(t for t, *_ in node["L3_ocr"]).lower()
            hits = sum(1 for w in ql.split() if w in text)
            if hits:
                scored.append((hits, node))
        scored.sort(key=lambda x: -x[0])
        return [n for _, n in scored[:k]]

    def find_on_screen(self, query, png_path=None):
        """いまの画面から query に一致するテキストの画面座標を返す
        (正確なコンピュータ操作のための照準)。"""
        own = png_path is None
        if own:
            png_path = take_screenshot()
        items, (iw, ih) = ocr_image(png_path)
        if own:
            os.unlink(png_path)
        ql = query.lower()
        matches = [(t, x, y, w, h) for t, x, y, w, h in items if ql in t.lower()]
        # Retina 補正: スクショはピクセル座標、クリックはポイント座標
        import Quartz
        main = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        scale = iw / main.size.width if main.size.width else 1.0
        return [(t, x / scale, y / scale, w / scale, h / scale) for t, x, y, w, h in matches]


def _top_words(words, k):
    freq = {}
    for w in words:
        w = w.strip()
        if len(w) >= 2:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:k]]


if __name__ == "__main__":
    vm = VisionMemory()
    node = vm.imprint_screen(label="manual test")
    print(f"[Vision] ノード #{node['id']} 刻印")
    print("  L1 署名:", node["L1_signature"])
    print("  L2 概念:", node["L2_concepts"])
    print("  OCR 要素数:", len(node["L3_ocr"]), "| 画面:", node["screen_px"])
    print("  L3 JPEG:", node["L3_jpeg"], f"({os.path.getsize(node['L3_jpeg'])//1024}KB)")
