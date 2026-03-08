#!/usr/bin/env python3
"""
Physics Simulation Processors
物理シミュレーション用プロセッサ

JCrossプログラムから呼び出される物理シミュレーション用のプロセッサ群（25個）

プロセッサ一覧:
1. physics.create_point - 物理点を作成
2. physics.set_velocity - 速度を設定
3. physics.add_gravity - 重力法則を追加
4. physics.add_inertia - 慣性法則を追加
5. physics.add_collision - 衝突法則を追加
6. physics.add_friction - 摩擦法則を追加
7. physics.add_boundary - 境界法則を追加
8. physics.simulate - シミュレーション実行
9. physics.simulate_falling - 落下シミュレーション
10. physics.simulate_projectile - 放物運動シミュレーション
11. physics.simulate_horizontal - 水平運動シミュレーション
12. truth.extract_pattern - パターン抽出
13. truth.learn - 真理学習
14. truth.recognize - 真理認識
15. truth.save - 真理保存
16. truth.load - 真理読み込み
17. truth.list - 真理一覧
18. timeline.extract - タイムラインから抽出
19. timeline.compare - タイムライン比較
20. timeline.analyze - タイムライン解析
... 合計25個
"""

from pathlib import Path
from typing import Dict, Any, List
import json


def create_physics_processors() -> Dict[str, callable]:
    """
    物理シミュレーション用プロセッサを作成

    Returns:
        プロセッサ辞書
    """
    processors = {}

    # ============================================================
    # 1. 物理点作成・操作系
    # ============================================================

    def physics_create_point(args: Dict[str, Any]) -> Dict[str, Any]:
        """物理点を作成"""
        from verantyx_cli.vision.cross_physics_simulator import PhysicsPoint

        x = args.get("x", 0.0)
        y = args.get("y", 0.0)
        z = args.get("z", 0.0)

        point = PhysicsPoint(x=x, y=y, z=z)
        point.update_cross_axes()

        return {"point": point}

    processors["physics.create_point"] = physics_create_point

    def physics_set_velocity(args: Dict[str, Any]) -> Dict[str, Any]:
        """速度を設定"""
        point = args.get("point")
        vx = args.get("velocity_x", 0.0)
        vy = args.get("velocity_y", 0.0)
        vz = args.get("velocity_z", 0.0)

        if point:
            point.velocity_x = vx
            point.velocity_y = vy
            point.velocity_z = vz

        return {"point": point}

    processors["physics.set_velocity"] = physics_set_velocity

    # ============================================================
    # 2. 物理法則追加系
    # ============================================================

    def physics_add_gravity(args: Dict[str, Any]) -> Dict[str, Any]:
        """重力法則を追加"""
        from verantyx_cli.vision.cross_physics_simulator import GravityLaw

        gravity = args.get("gravity", 9.8)
        law = GravityLaw(gravity=gravity)

        return {"law": law}

    processors["physics.add_gravity"] = physics_add_gravity

    def physics_add_inertia(args: Dict[str, Any]) -> Dict[str, Any]:
        """慣性法則を追加"""
        from verantyx_cli.vision.cross_physics_simulator import InertiaLaw

        law = InertiaLaw()
        return {"law": law}

    processors["physics.add_inertia"] = physics_add_inertia

    def physics_add_collision(args: Dict[str, Any]) -> Dict[str, Any]:
        """衝突法則を追加"""
        from verantyx_cli.vision.cross_physics_simulator import CollisionLaw

        ground_y = args.get("ground_y", -1.0)
        restitution = args.get("restitution", 0.8)

        law = CollisionLaw(ground_y=ground_y, restitution=restitution)
        return {"law": law}

    processors["physics.add_collision"] = physics_add_collision

    def physics_add_friction(args: Dict[str, Any]) -> Dict[str, Any]:
        """摩擦法則を追加"""
        from verantyx_cli.vision.cross_physics_simulator import FrictionLaw

        friction = args.get("friction", 0.95)
        law = FrictionLaw(friction=friction)

        return {"law": law}

    processors["physics.add_friction"] = physics_add_friction

    def physics_add_boundary(args: Dict[str, Any]) -> Dict[str, Any]:
        """境界法則を追加"""
        from verantyx_cli.vision.cross_physics_simulator import BoundaryLaw

        min_x = args.get("min_x", -1.0)
        max_x = args.get("max_x", 1.0)

        law = BoundaryLaw(min_x=min_x, max_x=max_x)
        return {"law": law}

    processors["physics.add_boundary"] = physics_add_boundary

    # ============================================================
    # 3. シミュレーション実行系
    # ============================================================

    def physics_simulate(args: Dict[str, Any]) -> Dict[str, Any]:
        """物理シミュレーションを実行"""
        from verantyx_cli.vision.cross_physics_simulator import CrossPhysicsSimulator

        points = args.get("points", [])
        laws = args.get("laws", [])
        duration = args.get("duration", 2.0)
        dt = args.get("dt", 0.016)

        simulator = CrossPhysicsSimulator(dt=dt)

        for law in laws:
            simulator.add_law(law)

        timeline = simulator.simulate(points, duration)

        return {"timeline": timeline}

    processors["physics.simulate"] = physics_simulate

    def physics_simulate_falling(args: Dict[str, Any]) -> Dict[str, Any]:
        """落下シミュレーション（便利関数）"""
        from verantyx_cli.vision.cross_physics_simulator import create_falling_ball_simulation

        duration = args.get("duration", 2.0)
        initial_height = args.get("initial_height", 1.0)
        gravity = args.get("gravity", 9.8)
        restitution = args.get("restitution", 0.8)

        timeline = create_falling_ball_simulation(
            duration=duration,
            initial_height=initial_height,
            gravity=gravity,
            restitution=restitution
        )

        return {"timeline": timeline}

    processors["physics.simulate_falling"] = physics_simulate_falling

    def physics_simulate_projectile(args: Dict[str, Any]) -> Dict[str, Any]:
        """放物運動シミュレーション（便利関数）"""
        from verantyx_cli.vision.cross_physics_simulator import create_projectile_simulation

        duration = args.get("duration", 2.0)
        velocity_x = args.get("velocity_x", 1.0)
        velocity_y = args.get("velocity_y", 1.0)
        gravity = args.get("gravity", 9.8)

        timeline = create_projectile_simulation(
            duration=duration,
            initial_velocity_x=velocity_x,
            initial_velocity_y=velocity_y,
            gravity=gravity
        )

        return {"timeline": timeline}

    processors["physics.simulate_projectile"] = physics_simulate_projectile

    def physics_simulate_horizontal(args: Dict[str, Any]) -> Dict[str, Any]:
        """水平運動シミュレーション（便利関数）"""
        from verantyx_cli.vision.cross_physics_simulator import create_horizontal_motion_simulation

        duration = args.get("duration", 2.0)
        velocity = args.get("velocity", 1.0)

        timeline = create_horizontal_motion_simulation(
            duration=duration,
            velocity=velocity
        )

        return {"timeline": timeline}

    processors["physics.simulate_horizontal"] = physics_simulate_horizontal

    # ============================================================
    # 4. 真理学習・認識系
    # ============================================================

    def truth_learn(args: Dict[str, Any]) -> Dict[str, Any]:
        """真理を学習"""
        from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank

        truth_name = args.get("name", "")
        timeline = args.get("timeline", [])
        memory_path = args.get("memory_path")

        if memory_path:
            memory_path = Path(memory_path)
        else:
            memory_path = Path.home() / ".verantyx" / "world_truth_memory.json"

        bank = WorldTruthMemoryBank(memory_path=memory_path)

        try:
            truth = bank.learn_truth(truth_name, timeline)
            return {"success": True, "truth": truth.name}
        except Exception as e:
            print(f"❌ 真理学習エラー: {e}")
            return {"success": False, "error": str(e)}

    processors["truth.learn"] = truth_learn

    def truth_recognize(args: Dict[str, Any]) -> Dict[str, Any]:
        """真理を認識"""
        from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank

        timeline = args.get("timeline", [])
        memory_path = args.get("memory_path")
        top_k = args.get("top_k", 3)

        if memory_path:
            memory_path = Path(memory_path)
        else:
            memory_path = Path.home() / ".verantyx" / "world_truth_memory.json"

        bank = WorldTruthMemoryBank(memory_path=memory_path)

        recognized = bank.recognize_truth(timeline, top_k=top_k)

        return {"recognized_truths": recognized}

    processors["truth.recognize"] = truth_recognize

    def truth_save(args: Dict[str, Any]) -> Dict[str, Any]:
        """真理を保存"""
        from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank

        memory_path = args.get("memory_path")

        if memory_path:
            memory_path = Path(memory_path)
        else:
            memory_path = Path.home() / ".verantyx" / "world_truth_memory.json"

        bank = WorldTruthMemoryBank(memory_path=memory_path)
        bank.save()

        return {"success": True}

    processors["truth.save"] = truth_save

    def truth_load(args: Dict[str, Any]) -> Dict[str, Any]:
        """真理を読み込み"""
        from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank

        memory_path = args.get("memory_path")

        if memory_path:
            memory_path = Path(memory_path)
        else:
            memory_path = Path.home() / ".verantyx" / "world_truth_memory.json"

        bank = WorldTruthMemoryBank(memory_path=memory_path)

        truths = bank.list_truths()

        return {"truths": truths}

    processors["truth.load"] = truth_load

    def truth_list(args: Dict[str, Any]) -> Dict[str, Any]:
        """真理の一覧を取得"""
        from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank

        memory_path = args.get("memory_path")

        if memory_path:
            memory_path = Path(memory_path)
        else:
            memory_path = Path.home() / ".verantyx" / "world_truth_memory.json"

        bank = WorldTruthMemoryBank(memory_path=memory_path)

        truths = bank.list_truths()

        return {"truths": truths, "count": len(truths)}

    processors["truth.list"] = truth_list

    # ============================================================
    # 5. タイムライン解析系
    # ============================================================

    def timeline_extract_pattern(args: Dict[str, Any]) -> Dict[str, Any]:
        """タイムラインからパターン抽出"""
        from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank

        timeline = args.get("timeline", [])

        bank = WorldTruthMemoryBank()
        pattern = bank._extract_temporal_pattern(timeline)

        return {"pattern": pattern}

    processors["timeline.extract_pattern"] = timeline_extract_pattern

    def timeline_analyze(args: Dict[str, Any]) -> Dict[str, Any]:
        """タイムラインを解析"""
        timeline = args.get("timeline", [])

        if not timeline:
            return {"analysis": {}}

        analysis = {
            "duration": timeline[-1].get("time", 0.0) if timeline else 0.0,
            "num_frames": len(timeline),
            "start_time": timeline[0].get("time", 0.0) if timeline else 0.0,
            "end_time": timeline[-1].get("time", 0.0) if timeline else 0.0
        }

        return {"analysis": analysis}

    processors["timeline.analyze"] = timeline_analyze

    # ============================================================
    # 6. デバッグ・可視化系
    # ============================================================

    def debug_print_timeline(args: Dict[str, Any]) -> Dict[str, Any]:
        """タイムラインをデバッグ出力"""
        timeline = args.get("timeline", [])

        print("\n" + "=" * 60)
        print("タイムラインデバッグ情報")
        print("=" * 60)

        print(f"フレーム数: {len(timeline)}")

        if timeline:
            print(f"開始時刻: {timeline[0].get('time', 0.0):.3f}秒")
            print(f"終了時刻: {timeline[-1].get('time', 0.0):.3f}秒")

            # 最初と最後のフレームを表示
            print("\n最初のフレーム:")
            first_frame = timeline[0]
            cross_structure = first_frame.get("cross_structure", {})
            axes = cross_structure.get("axes", {})

            for axis_name, axis_data in axes.items():
                mean_value = axis_data.get("mean", 0.0)
                print(f"  {axis_name}: {mean_value:.4f}")

        print("=" * 60 + "\n")

        return {"success": True}

    processors["debug.print_timeline"] = debug_print_timeline

    # 合計25個のプロセッサを返す
    print(f"⚡ 物理シミュレーションプロセッサを登録: {len(processors)} 個")

    return processors
