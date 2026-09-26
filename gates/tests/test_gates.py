"""对拍测试: 用与引擎完全独立的"射线法 + Python 集合运算"作为参照实现,
在随机小点集上逐门核对 hitIds / count / 命中向量。

引擎内部使用半平面叉积法; 参照实现使用经典水平射线法(浮点),
两者算法路径相互独立, 边界点则由双方各自的共线段判定负责。
"""

from __future__ import annotations

import math
import random

import pytest

from app.gates import (
    MAX_GATES,
    MAX_POINTS,
    ValidationError,
    cross,
    evaluate,
)


# ---------------------------------------------------------------------------
# 独立参照实现
# ---------------------------------------------------------------------------

def _ref_on_segment(px, py, a, b) -> bool:
    ax, ay = a
    bx, by = b
    if cross(ax, ay, bx, by, px, py) != 0:
        return False
    return min(ax, bx) <= px <= max(ax, bx) and min(ay, by) <= py <= max(ay, by)


def ref_point_in_polygon(px, py, vertices) -> bool:
    """射线法(向 +x 发射), 先判边界。独立于引擎的半平面法。"""
    n = len(vertices)
    for i in range(n):
        if _ref_on_segment(px, py, vertices[i], vertices[(i + 1) % n]):
            return True

    inside = False
    for i in range(n):
        ax, ay = vertices[i]
        bx, by = vertices[(i + 1) % n]
        if (ay > py) != (by > py):
            x_cross = ax + (bx - ax) * (py - ay) / (by - ay)
            if px < x_cross:
                inside = not inside
    return inside


def ref_apply(op: str, left: set, right: set) -> set:
    # 显式写一遍, 不走引擎里的同一份运算。
    if op == "AND":
        return {x for x in left if x in right}
    if op == "OR":
        return {x for x in left} | {x for x in right}
    if op == "DIFF":
        return {x for x in left if x not in right}
    raise AssertionError(op)


# ---------------------------------------------------------------------------
# 随机凸多边形生成(按极角排序保证环向凸)
# ---------------------------------------------------------------------------

def random_convex_polygon(rng: random.Random):
    """生成按极角排序的凸多边形; 整数四舍五入后可能轻微退化,
    因此用整数叉积独立复核环向凸与非零面积, 退化则重试。"""
    for _ in range(200):
        n = rng.randint(3, 8)
        angles = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
        cx, cy = rng.randint(30, 70), rng.randint(30, 70)
        verts = []
        ok = True
        for ang in angles:
            r = rng.randint(8, 28)
            x = int(round(cx + r * math.cos(ang)))
            y = int(round(cy + r * math.sin(ang)))
            if not (0 <= x <= 100 and 0 <= y <= 100):
                ok = False
                break
            verts.append((x, y))
        if not ok or len(set(verts)) != n:
            continue
        area2 = 0
        signs = set()
        for i in range(n):
            ax, ay = verts[i]
            bx, by = verts[(i + 1) % n]
            cx2, cy2 = verts[(i + 2) % n]
            c = cross(ax, ay, bx, by, cx2, cy2)
            if c != 0:
                signs.add(1 if c > 0 else -1)
            area2 += ax * by - bx * ay
        if area2 != 0 and len(signs) == 1:
            return [list(v) for v in verts]
    raise AssertionError("无法生成合法随机凸多边形")


def build_random_case(seed: int):
    rng = random.Random(seed)
    n_points = rng.randint(0, 40)
    # 0~100 的网格让边界面/附近有更大概率取到点。
    points = []
    used = set()
    pid = 0
    while len(points) < n_points:
        size = rng.randint(0, 100)
        intensity = rng.randint(0, 100)
        if (size, intensity) in used:
            continue
        used.add((size, intensity))
        points.append({"id": pid, "size": size, "intensity": intensity})
        pid += 1

    n_poly = rng.randint(1, 4)
    poly_vertices = [random_convex_polygon(rng) for _ in range(n_poly)]
    gates = [
        {"id": f"P{i}", "type": "polygon", "vertices": poly_vertices[i]}
        for i in range(n_poly)
    ]

    # 参照集合(独立射线法)。
    ref_sets = {}
    for i, verts in enumerate(poly_vertices):
        ref_sets[f"P{i}"] = {
            p["id"]
            for p in points
            if ref_point_in_polygon(p["size"], p["intensity"], verts)
        }

    n_combo = rng.randint(0, 3)
    for j in range(n_combo):
        op = rng.choice(["AND", "OR", "DIFF"])
        # 只引用更早的门(含已生成的组合门)。
        earlier = [g["id"] for g in gates]
        left = rng.choice(earlier)
        right = rng.choice(earlier)
        gid = f"C{j}"
        gates.append(
            {"id": gid, "type": "combine", "op": op, "left": left, "right": right}
        )
        ref_sets[gid] = ref_apply(op, ref_sets[left], ref_sets[right])

    return {"points": points, "gates": gates}, ref_sets


# ---------------------------------------------------------------------------
# 对拍
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(60))
def test_random_cases_match_reference(seed):
    payload, ref_sets = build_random_case(seed)
    result = evaluate(payload)

    assert [g["id"] for g in result["gates"]] == list(ref_sets)

    point_ids_sorted = sorted(p["id"] for p in payload["points"])
    assert [v["id"] for v in result["vectors"]] == point_ids_sorted

    for col, gate in enumerate(result["gates"]):
        expected = ref_sets[gate["id"]]
        assert gate["hitIds"] == sorted(expected)
        assert gate["count"] == len(expected)

        by_id = {v["id"]: v["hits"] for v in result["vectors"]}
        for pid in point_ids_sorted:
            vec = by_id[pid]
            assert len(vec) == len(result["gates"])
            assert vec[col] == (1 if pid in expected else 0)


def test_boundary_points_are_hits():
    """矩形的四个角与四条边上的点都算命中。"""
    verts = [[10, 10], [40, 10], [40, 40], [10, 40]]
    edge_points = [
        (10, 10), (40, 10), (40, 40), (10, 40),  # 角点
        (25, 10), (40, 25), (25, 40), (10, 25),  # 边中点
        (10, 30), (30, 40),
    ]
    payload = {
        "points": [
            {"id": i, "size": s, "intensity": t}
            for i, (s, t) in enumerate(edge_points)
        ],
        "gates": [{"id": "rect", "type": "polygon", "vertices": verts}],
    }
    result = evaluate(payload)
    assert result["gates"][0]["hitIds"] == list(range(len(edge_points)))
    assert result["gates"][0]["count"] == len(edge_points)
    assert all(v["hits"] == [1] for v in result["vectors"])


def test_clockwise_and_ccw_polygons_equivalent():
    ccw = [[0, 0], [10, 0], [10, 10], [0, 10]]
    cw = list(reversed(ccw))
    points = [
        {"id": 0, "size": 5, "intensity": 5},
        {"id": 1, "size": 0, "intensity": 0},
        {"id": 2, "size": 50, "intensity": 50},
    ]
    r_ccw = evaluate({"points": points, "gates": [
        {"id": "g", "type": "polygon", "vertices": ccw}]})
    r_cw = evaluate({"points": points, "gates": [
        {"id": "g", "type": "polygon", "vertices": cw}]})
    assert r_ccw["gates"][0]["hitIds"] == r_cw["gates"][0]["hitIds"] == [0, 1]


def test_triangle_with_collinear_vertex_ok():
    """边上的共线顶点允许存在, 面积仍非零。"""
    verts = [[0, 0], [5, 0], [10, 0], [10, 10]]
    result = evaluate({
        "points": [{"id": 0, "size": 5, "intensity": 0}],
        "gates": [{"id": "g", "type": "polygon", "vertices": verts}],
    })
    assert result["gates"][0]["hitIds"] == [0]


def test_point_on_other_subsegment_of_collinear_chain():
    """底边由 3 个连续共线顶点组成: 点在第二条子段上(对第一条边的支撑线
    共线但不在其段内), 仍必须算命中; 支撑线延长方向上的外部点必须排除。
    (seed 17 对拍回归)"""
    verts = [[49, 69], [44, 67], [31, 61], [22, 38], [36, 38], [62, 38]]
    points = [
        {"id": 0, "size": 53, "intensity": 38},   # 底边上第二条子段
        {"id": 1, "size": 22, "intensity": 38},   # 底边左端点
        {"id": 2, "size": 70, "intensity": 38},   # 支撑线向右延长, 外部
        {"id": 3, "size": 10, "intensity": 38},   # 支撑线向左延长, 外部
    ]
    hit = evaluate({
        "points": points,
        "gates": [{"id": "g", "type": "polygon", "vertices": verts}],
    })["gates"][0]
    assert hit["hitIds"] == [0, 1]


def test_diff_is_left_minus_right():
    # A: 矩形 [0,0]-[10,10]; B: 矩形 [5,0]-[15,10]
    points = [
        {"id": 1, "size": 2, "intensity": 5},   # 仅 A
        {"id": 2, "size": 7, "intensity": 5},   # A∩B
        {"id": 3, "size": 12, "intensity": 5},  # 仅 B
    ]
    payload = {
        "points": points,
        "gates": [
            {"id": "A", "type": "polygon",
             "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"id": "B", "type": "polygon",
             "vertices": [[5, 0], [15, 0], [15, 10], [5, 10]]},
            {"id": "AminusB", "type": "combine",
             "op": "DIFF", "left": "A", "right": "B"},
            {"id": "BminusA", "type": "combine",
             "op": "DIFF", "left": "B", "right": "A"},
            {"id": "andg", "type": "combine",
             "op": "AND", "left": "A", "right": "B"},
            {"id": "org", "type": "combine",
             "op": "OR", "left": "A", "right": "B"},
        ],
    }
    gates = {g["id"]: g for g in evaluate(payload)["gates"]}
    assert gates["AminusB"]["hitIds"] == [1]
    assert gates["BminusA"]["hitIds"] == [3]
    assert gates["andg"]["hitIds"] == [2]
    assert gates["org"]["hitIds"] == [1, 2, 3]
    # 向量列顺序与门顺序一致。
    vectors = {v["id"]: v["hits"] for v in evaluate(payload)["vectors"]}
    assert vectors[1] == [1, 0, 1, 0, 0, 1]
    assert vectors[2] == [1, 1, 0, 0, 1, 1]
    assert vectors[3] == [0, 1, 0, 1, 0, 1]


# ---------------------------------------------------------------------------
# 422 校验
# ---------------------------------------------------------------------------

def _expect_422(payload):
    with pytest.raises(ValidationError):
        evaluate(payload)


def test_duplicate_point_id():
    _expect_422({
        "points": [
            {"id": 1, "size": 0, "intensity": 0},
            {"id": 1, "size": 1, "intensity": 1},
        ],
        "gates": [],
    })


def test_duplicate_gate_id():
    _expect_422({
        "points": [],
        "gates": [
            {"id": "g", "type": "polygon", "vertices": [[0, 0], [1, 0], [1, 1]]},
            {"id": "g", "type": "polygon", "vertices": [[0, 0], [2, 0], [2, 2]]},
        ],
    })


def test_forward_and_unknown_reference_rejected():
    base_poly = {"id": "a", "type": "polygon",
                 "vertices": [[0, 0], [10, 0], [10, 10]]}
    # 引用尚未定义(逆向)的门
    _expect_422({
        "points": [],
        "gates": [
            {"id": "c", "type": "combine", "op": "AND", "left": "a", "right": "b"},
            base_poly,
        ],
    })
    # 自引用同样非法
    _expect_422({
        "points": [],
        "gates": [
            {"id": "c", "type": "combine", "op": "AND", "left": "c", "right": "c"},
        ],
    })
    # 完全未知
    _expect_422({
        "points": [],
        "gates": [
            base_poly,
            {"id": "c", "type": "combine", "op": "OR", "left": "a", "right": "x"},
        ],
    })


def test_extra_fields_rejected():
    tri = {"id": "g", "type": "polygon",
           "vertices": [[0, 0], [10, 0], [10, 10]]}
    _expect_422({"points": [], "gates": [], "extra": 1})
    _expect_422({"points": [{"id": 0, "size": 0, "intensity": 0, "q": 1}],
                 "gates": []})
    bad = dict(tri)
    bad["color"] = "red"
    _expect_422({"points": [], "gates": [bad]})
    # 顶点出现第三个坐标
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon",
         "vertices": [[0, 0, 0], [10, 0], [10, 10]]}]})
    # 组合门多余字段
    _expect_422({"points": [], "gates": [
        tri,
        {"id": "c", "type": "combine", "op": "AND",
         "left": "g", "right": "g", "weight": 2},
    ]})


def test_bad_polygon_shapes():
    # 非凸(箭头四边形)
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon",
         "vertices": [[0, 0], [10, 0], [2, 2], [0, 10]]}]})
    # 零面积(全部共线)
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon",
         "vertices": [[0, 0], [5, 0], [10, 0]]}]})
    # 重复顶点
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon",
         "vertices": [[0, 0], [10, 0], [10, 10], [0, 0]]}]})
    # 顶点数 2
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon", "vertices": [[0, 0], [10, 0]]}]})
    # 顶点数 13(在文件下方定义的 _convex_n 按整圆取点)
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon", "vertices": _convex_n(13)}]})


def _convex_n(n):
    pts = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        pts.append([round(50 + 40 * math.cos(ang)), round(50 + 40 * math.sin(ang))])
    return pts


def test_range_and_type_validation():
    ok = {"points": [], "gates": []}
    assert evaluate(ok)["gates"] == []
    _expect_422({"points": [{"id": 0, "size": -1, "intensity": 0}], "gates": []})
    _expect_422({"points": [{"id": 0, "size": 0, "intensity": 1001}], "gates": []})
    _expect_422({"points": [{"id": True, "size": 0, "intensity": 0}], "gates": []})
    _expect_422({"points": [{"id": 0.5, "size": 0, "intensity": 0}], "gates": []})
    _expect_422({"points": "nope", "gates": []})
    _expect_422({"points": [], "gates": "nope"})
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon",
         "vertices": [[0, 0], [1001, 0], [10, 10]]}]})
    _expect_422({"points": [], "gates": [
        {"id": "", "type": "polygon",
         "vertices": [[0, 0], [10, 0], [10, 10]]}]})
    _expect_422({"points": [], "gates": [
        {"id": 5, "type": "polygon",
         "vertices": [[0, 0], [10, 0], [10, 10]]}]})
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "warp",
         "vertices": [[0, 0], [10, 0], [10, 10]]}]})
    _expect_422({"points": [], "gates": [
        {"id": "g", "vertices": [[0, 0], [10, 0], [10, 10]]}]})


def test_malformed_structures_do_not_500():
    """非数组/含 null 的畸形结构必须走 422, 而不是在 len/排序处抛 TypeError。"""
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon", "vertices": None}]})
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon", "vertices": 3}]})
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon",
         "vertices": [[0, 0], None, [10, 10]]}]})
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon", "vertices": []}]})
    _expect_422({"points": [], "gates": [
        {"id": "g", "type": "polygon",
         "vertices": [[0, 0], [10, 0], [10, 10]], "op": None}]})
    _expect_422({"points": [], "gates": [
        {"id": 42, "type": "polygon"}]})
    _expect_422({"points": [None], "gates": []})


def test_bad_op_and_ref_types():
    tri = {"id": "a", "type": "polygon",
           "vertices": [[0, 0], [10, 0], [10, 10]]}
    _expect_422({"points": [], "gates": [
        tri, {"id": "c", "type": "combine", "op": "XOR",
              "left": "a", "right": "a"}]})
    _expect_422({"points": [], "gates": [
        tri, {"id": "c", "type": "combine", "op": "AND",
              "left": 3, "right": "a"}]})
    _expect_422({"points": [], "gates": [
        tri, {"id": "c", "type": "combine", "op": "AND",
              "left": "a"}]})


def test_limits_enforced():
    pts = [{"id": i, "size": 0, "intensity": 0} for i in range(MAX_POINTS + 1)]
    _expect_422({"points": pts, "gates": []})
    gates = [
        {"id": f"g{i}", "type": "polygon",
         "vertices": [[0, 0], [1, 0], [1, 1]]}
        for i in range(MAX_GATES + 1)
    ]
    _expect_422({"points": [], "gates": gates})
    # 恰好 5000 点 / 20 门应当通过
    pts_ok = [{"id": i, "size": 0, "intensity": 0} for i in range(MAX_POINTS)]
    gates_ok = gates[:MAX_GATES]
    result = evaluate({"points": pts_ok, "gates": gates_ok})
    assert len(result["gates"]) == MAX_GATES
    assert result["gates"][0]["count"] == MAX_POINTS
    assert all(len(v["hits"]) == MAX_GATES for v in result["vectors"])
