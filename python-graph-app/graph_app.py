#!/usr/bin/env python3
"""
グラフアプリケーション
matplotlib と tkinter を使用したインタラクティブなグラフ描画アプリ
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import json
from datetime import datetime


class GraphApp:
    """グラフアプリケーションのメインクラス"""

    def __init__(self, root):
        self.root = root
        self.root.title("グラフアプリケーション")
        self.root.geometry("1200x800")

        # データ保存用
        self.data_points = []
        self.current_graph_type = "折れ線グラフ"

        # UIの構築
        self.setup_ui()

        # サンプルデータの読み込み
        self.load_sample_data()

    def setup_ui(self):
        """UIコンポーネントのセットアップ"""

        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 左側: コントロールパネル
        control_frame = ttk.LabelFrame(main_frame, text="コントロールパネル", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # グラフタイプ選択
        ttk.Label(control_frame, text="グラフの種類:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.graph_type = ttk.Combobox(control_frame, values=[
            "折れ線グラフ",
            "棒グラフ",
            "散布図",
            "円グラフ",
            "ヒストグラム",
            "箱ひげ図"
        ], state="readonly", width=20)
        self.graph_type.set("折れ線グラフ")
        self.graph_type.grid(row=0, column=1, pady=5)
        self.graph_type.bind("<<ComboboxSelected>>", lambda e: self.update_graph())

        # データ入力セクション
        ttk.Separator(control_frame, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        ttk.Label(control_frame, text="データ入力", font=('', 10, 'bold')).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

        # X値入力
        ttk.Label(control_frame, text="X値:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.x_entry = ttk.Entry(control_frame, width=22)
        self.x_entry.grid(row=3, column=1, pady=5)

        # Y値入力
        ttk.Label(control_frame, text="Y値:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.y_entry = ttk.Entry(control_frame, width=22)
        self.y_entry.grid(row=4, column=1, pady=5)

        # ラベル入力
        ttk.Label(control_frame, text="ラベル:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.label_entry = ttk.Entry(control_frame, width=22)
        self.label_entry.grid(row=5, column=1, pady=5)

        # ボタン
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="追加", command=self.add_data_point).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="クリア", command=self.clear_data).pack(side=tk.LEFT, padx=5)

        # データリスト
        ttk.Separator(control_frame, orient='horizontal').grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        ttk.Label(control_frame, text="データ一覧", font=('', 10, 'bold')).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=5)

        # データリストボックス
        list_frame = ttk.Frame(control_frame)
        list_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.data_listbox = tk.Listbox(list_frame, height=10, yscrollcommand=scrollbar.set)
        self.data_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.data_listbox.yview)

        # 削除ボタン
        ttk.Button(control_frame, text="選択項目を削除", command=self.delete_selected).grid(row=10, column=0, columnspan=2, pady=5)

        # グラフオプション
        ttk.Separator(control_frame, orient='horizontal').grid(row=11, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        ttk.Label(control_frame, text="グラフオプション", font=('', 10, 'bold')).grid(row=12, column=0, columnspan=2, sticky=tk.W, pady=5)

        # タイトル
        ttk.Label(control_frame, text="タイトル:").grid(row=13, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(control_frame, width=22)
        self.title_entry.insert(0, "グラフ")
        self.title_entry.grid(row=13, column=1, pady=5)
        self.title_entry.bind("<KeyRelease>", lambda e: self.update_graph())

        # X軸ラベル
        ttk.Label(control_frame, text="X軸:").grid(row=14, column=0, sticky=tk.W, pady=5)
        self.xlabel_entry = ttk.Entry(control_frame, width=22)
        self.xlabel_entry.insert(0, "X")
        self.xlabel_entry.grid(row=14, column=1, pady=5)
        self.xlabel_entry.bind("<KeyRelease>", lambda e: self.update_graph())

        # Y軸ラベル
        ttk.Label(control_frame, text="Y軸:").grid(row=15, column=0, sticky=tk.W, pady=5)
        self.ylabel_entry = ttk.Entry(control_frame, width=22)
        self.ylabel_entry.insert(0, "Y")
        self.ylabel_entry.grid(row=15, column=1, pady=5)
        self.ylabel_entry.bind("<KeyRelease>", lambda e: self.update_graph())

        # グリッド表示
        self.show_grid = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="グリッド表示", variable=self.show_grid,
                       command=self.update_graph).grid(row=16, column=0, columnspan=2, sticky=tk.W, pady=5)

        # 凡例表示
        self.show_legend = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="凡例表示", variable=self.show_legend,
                       command=self.update_graph).grid(row=17, column=0, columnspan=2, sticky=tk.W, pady=5)

        # ファイル操作
        ttk.Separator(control_frame, orient='horizontal').grid(row=18, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        file_button_frame = ttk.Frame(control_frame)
        file_button_frame.grid(row=19, column=0, columnspan=2, pady=5)

        ttk.Button(file_button_frame, text="保存", command=self.save_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="読込", command=self.load_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="画像保存", command=self.save_image).pack(side=tk.LEFT, padx=5)

        # 右側: グラフ表示エリア
        graph_frame = ttk.LabelFrame(main_frame, text="グラフ", padding="10")
        graph_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # グラフの作成
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)

        # キャンバスの作成
        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ツールバーの追加
        toolbar = NavigationToolbar2Tk(self.canvas, graph_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ウィンドウのリサイズ設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

    def add_data_point(self):
        """データポイントを追加"""
        try:
            x_val = float(self.x_entry.get())
            y_val = float(self.y_entry.get())
            label = self.label_entry.get() or f"データ{len(self.data_points) + 1}"

            self.data_points.append({"x": x_val, "y": y_val, "label": label})
            self.update_data_list()
            self.update_graph()

            # 入力欄をクリア
            self.x_entry.delete(0, tk.END)
            self.y_entry.delete(0, tk.END)
            self.label_entry.delete(0, tk.END)

        except ValueError:
            messagebox.showerror("エラー", "X値とY値は数値で入力してください")

    def delete_selected(self):
        """選択されたデータを削除"""
        selection = self.data_listbox.curselection()
        if selection:
            index = selection[0]
            del self.data_points[index]
            self.update_data_list()
            self.update_graph()

    def clear_data(self):
        """全データをクリア"""
        if messagebox.askyesno("確認", "すべてのデータをクリアしますか？"):
            self.data_points = []
            self.update_data_list()
            self.update_graph()

    def update_data_list(self):
        """データリストボックスを更新"""
        self.data_listbox.delete(0, tk.END)
        for i, point in enumerate(self.data_points):
            self.data_listbox.insert(tk.END, f"{point['label']}: ({point['x']}, {point['y']})")

    def update_graph(self):
        """グラフを更新"""
        self.ax.clear()

        if not self.data_points:
            self.ax.text(0.5, 0.5, 'データがありません',
                        ha='center', va='center', transform=self.ax.transAxes,
                        fontsize=12, color='gray')
            self.canvas.draw()
            return

        # データの抽出
        x_data = [p['x'] for p in self.data_points]
        y_data = [p['y'] for p in self.data_points]
        labels = [p['label'] for p in self.data_points]

        # グラフタイプに応じて描画
        graph_type = self.graph_type.get()

        if graph_type == "折れ線グラフ":
            self.ax.plot(x_data, y_data, marker='o', linestyle='-', linewidth=2, markersize=8)

        elif graph_type == "棒グラフ":
            self.ax.bar(labels, y_data, color='steelblue', alpha=0.7)
            self.ax.set_xticks(range(len(labels)))
            self.ax.set_xticklabels(labels, rotation=45, ha='right')

        elif graph_type == "散布図":
            self.ax.scatter(x_data, y_data, s=100, alpha=0.6, c='steelblue', edgecolors='black')
            for i, label in enumerate(labels):
                self.ax.annotate(label, (x_data[i], y_data[i]),
                               xytext=(5, 5), textcoords='offset points', fontsize=8)

        elif graph_type == "円グラフ":
            # 円グラフはY値のみ使用
            self.ax.pie(y_data, labels=labels, autopct='%1.1f%%', startangle=90)
            self.ax.axis('equal')

        elif graph_type == "ヒストグラム":
            self.ax.hist(y_data, bins=min(10, len(y_data)), color='steelblue', alpha=0.7, edgecolor='black')

        elif graph_type == "箱ひげ図":
            self.ax.boxplot(y_data, vert=True, patch_artist=True,
                          boxprops=dict(facecolor='lightblue', alpha=0.7))

        # グラフの設定
        if graph_type != "円グラフ":
            self.ax.set_xlabel(self.xlabel_entry.get(), fontsize=12)
            self.ax.set_ylabel(self.ylabel_entry.get(), fontsize=12)

            if self.show_grid.get():
                self.ax.grid(True, alpha=0.3)

        self.ax.set_title(self.title_entry.get(), fontsize=14, fontweight='bold')

        # 日本語フォントの設定（macOSの場合）
        plt.rcParams['font.sans-serif'] = ['Hiragino Sans', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

        self.figure.tight_layout()
        self.canvas.draw()

    def load_sample_data(self):
        """サンプルデータの読み込み"""
        sample_data = [
            {"x": 1, "y": 10, "label": "1月"},
            {"x": 2, "y": 15, "label": "2月"},
            {"x": 3, "y": 13, "label": "3月"},
            {"x": 4, "y": 18, "label": "4月"},
            {"x": 5, "y": 22, "label": "5月"},
            {"x": 6, "y": 25, "label": "6月"},
        ]
        self.data_points = sample_data
        self.update_data_list()
        self.update_graph()

    def save_data(self):
        """データをJSONファイルに保存"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        'data': self.data_points,
                        'title': self.title_entry.get(),
                        'xlabel': self.xlabel_entry.get(),
                        'ylabel': self.ylabel_entry.get(),
                        'graph_type': self.graph_type.get()
                    }, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", "データを保存しました")
            except Exception as e:
                messagebox.showerror("エラー", f"保存に失敗しました: {e}")

    def load_data(self):
        """JSONファイルからデータを読み込み"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.data_points = data.get('data', [])
                    self.title_entry.delete(0, tk.END)
                    self.title_entry.insert(0, data.get('title', 'グラフ'))
                    self.xlabel_entry.delete(0, tk.END)
                    self.xlabel_entry.insert(0, data.get('xlabel', 'X'))
                    self.ylabel_entry.delete(0, tk.END)
                    self.ylabel_entry.insert(0, data.get('ylabel', 'Y'))
                    self.graph_type.set(data.get('graph_type', '折れ線グラフ'))
                    self.update_data_list()
                    self.update_graph()
                messagebox.showinfo("成功", "データを読み込みました")
            except Exception as e:
                messagebox.showerror("エラー", f"読み込みに失敗しました: {e}")

    def save_image(self):
        """グラフを画像として保存"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("PDF files", "*.pdf"),
                ("SVG files", "*.svg"),
                ("All files", "*.*")
            ]
        )
        if filename:
            try:
                self.figure.savefig(filename, dpi=300, bbox_inches='tight')
                messagebox.showinfo("成功", "画像を保存しました")
            except Exception as e:
                messagebox.showerror("エラー", f"保存に失敗しました: {e}")


def main():
    """メイン関数"""
    root = tk.Tk()
    app = GraphApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
