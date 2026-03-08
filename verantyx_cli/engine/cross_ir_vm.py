"""
CrossIR Virtual Machine

CrossIR命令を順次実行するVMです。
JCrossプログラムをシーケンシャルに実行します。
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# kofdai_computer をインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "kofdai_computer"))

from cross_ir import Op, Instr, ProgramIR
from kernel import KofdaiKernel


class CrossIRVM:
    """
    CrossIR仮想マシン

    スタックベースのVM。CrossIR命令を順次実行します。
    """

    def __init__(self, program: ProgramIR, kernel: Optional[KofdaiKernel] = None, processors: Optional[Dict[str, callable]] = None):
        self.program = program
        self.kernel = kernel or KofdaiKernel()
        self.processors = processors or {}  # プロセッサ辞書: name -> function

        # VM状態
        self.stack: List[Any] = []
        self.variables: Dict[str, Any] = {}
        self.queues: Dict[str, List[Any]] = {}
        self.pc = 0  # Program counter
        self.running = True

    def run(self) -> Any:
        """プログラムを実行"""
        while self.running and self.pc < len(self.program.instructions):
            instr = self.program.instructions[self.pc]
            self.execute_instruction(instr)

        # スタックのトップを返す（あれば）
        return self.stack[-1] if self.stack else None

    def execute_instruction(self, instr: Instr):
        """1命令を実行"""
        op = instr.op

        # ═══════════════════════════════════════════════════════════
        # 基本命令
        # ═══════════════════════════════════════════════════════════

        if op == Op.NOP:
            self.pc += 1

        elif op == Op.HALT:
            self.running = False

        elif op == Op.PUSH:
            self.stack.append(instr.arg)
            self.pc += 1

        elif op == Op.POP:
            if self.stack:
                self.stack.pop()
            self.pc += 1

        elif op == Op.DUP:
            if self.stack:
                self.stack.append(self.stack[-1])
            self.pc += 1

        elif op == Op.SWAP:
            if len(self.stack) >= 2:
                self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
            self.pc += 1

        elif op == Op.ADD:
            if len(self.stack) >= 2:
                b = self.stack.pop()
                a = self.stack.pop()
                # 数値、文字列、リストの加算をサポート
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    self.stack.append(a + b)
                elif isinstance(a, str) and isinstance(b, str):
                    self.stack.append(a + b)
                elif isinstance(a, list) and isinstance(b, list):
                    self.stack.append(a + b)
                else:
                    self.stack.append(str(a) + str(b))
            self.pc += 1

        elif op == Op.GT:
            if len(self.stack) >= 2:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a > b else 0)
            self.pc += 1

        # ═══════════════════════════════════════════════════════════
        # 制御命令
        # ═══════════════════════════════════════════════════════════

        elif op == Op.JMP:
            label = instr.arg
            if label in self.program.labels:
                self.pc = self.program.labels[label]
            else:
                raise RuntimeError(f"Label not found: {label}")

        elif op == Op.JZ:
            # ゼロならジャンプ
            if self.stack:
                cond = self.stack.pop()
                if not cond or cond == 0:
                    label = instr.arg
                    if label in self.program.labels:
                        self.pc = self.program.labels[label]
                    else:
                        raise RuntimeError(f"Label not found: {label}")
                else:
                    self.pc += 1
            else:
                self.pc += 1

        elif op == Op.JNZ:
            # 非ゼロならジャンプ
            if self.stack:
                cond = self.stack.pop()
                if cond and cond != 0:
                    label = instr.arg
                    if label in self.program.labels:
                        self.pc = self.program.labels[label]
                    else:
                        raise RuntimeError(f"Label not found: {label}")
                else:
                    self.pc += 1
            else:
                self.pc += 1

        # ═══════════════════════════════════════════════════════════
        # 変数操作
        # ═══════════════════════════════════════════════════════════

        elif op == Op.SET:
            # stack: (key, value) -> value
            if len(self.stack) >= 2:
                value = self.stack.pop()
                key = self.stack.pop()
                self.variables[str(key)] = value
                self.stack.append(value)
            self.pc += 1

        elif op == Op.GET:
            # stack: (key) -> value
            if self.stack:
                key = self.stack.pop()
                value = self.variables.get(str(key), None)
                self.stack.append(value)
            self.pc += 1

        # ═══════════════════════════════════════════════════════════
        # プロセッサ呼び出し
        # ═══════════════════════════════════════════════════════════

        elif op == Op.PROC_CALL:
            # stack: (proc_name, args) -> result
            if len(self.stack) >= 2:
                args = self.stack.pop()
                proc_name = str(self.stack.pop())

                # プロセッサを呼び出し
                if proc_name in self.processors:
                    proc_func = self.processors[proc_name]
                    result = proc_func(args if isinstance(args, dict) else {})
                    self.stack.append(result)
                else:
                    print(f"⚠️  Processor not found: {proc_name}", flush=True)
                    self.stack.append(None)
            self.pc += 1

        # ═══════════════════════════════════════════════════════════
        # ユーティリティ
        # ═══════════════════════════════════════════════════════════

        elif op == Op.PRINT:
            if self.stack:
                value = self.stack.pop()
                print(value, flush=True)
            self.pc += 1

        # ═══════════════════════════════════════════════════════════
        # データ構造操作
        # ═══════════════════════════════════════════════════════════

        elif op == Op.DICT_GET:
            # stack: (dict, key) -> value
            if len(self.stack) >= 2:
                key = self.stack.pop()
                d = self.stack.pop()
                if isinstance(d, dict):
                    value = d.get(key, None)
                    self.stack.append(value)
                else:
                    self.stack.append(None)
            self.pc += 1

        # ═══════════════════════════════════════════════════════════
        # 未実装命令
        # ═══════════════════════════════════════════════════════════

        else:
            print(f"⚠️  Unimplemented instruction: {op}")
            self.pc += 1
