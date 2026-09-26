"""颗粒门控计算引擎。

输入: 至多 5000 个唯一 id 的整数点 (size, intensity), 坐标 0~1000;
至多 20 个门, 按顺序定义。门有两种:

* 凸多边形 (type="polygon"): 3~12 个不重复顶点, 顶点按环向(顺时针或逆时针)
  排列, 非零面积; 边界点算命中。
* 组合门 (type="combine"): 引用两个更早出现的门, op 为 AND / OR / DIFF
  (左集减右集)。

任何未知字段、未知/逆向引用、重复 id、非凸多边形等都会抛出 ValidationError,
由 HTTP 层映射为 422。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_POINTS = 5000
MAX_GATES = 20
MIN_VERTICES = 3
MAX_VERTICES = 12
COORD_MIN = 0
COORD_MAX = 1000

VALID_OPS = ("AND", "OR", "DIFF")
GATE_TYPES = ("polygon", "combine")

_TOP_KEYS = {"points", "gates"}
_POINT_KEYS = {"id", "size", "intensity"}
_GATE_KEYS = {"id", "type"}
_POLYGON_KEYS = {"id", "type", "vertices"}
_COMBINE_KEYS = {"id", "type", "op", "left", "right"}


class ValidationError(Exception):
    """输入不合法, 对应 HTTP 422。"""


@dataclass(frozen=True)
class Point:
    id: int
    size: int
    intensity: int


def _is_int(value) -> bool:
    # bool 是 int 的子类, 但 true/false 不应被当作坐标或 id。
    return isinstance(value, int) and not isinstance(value, bool)


def _coord_ok(value) -> bool:
    return _is_int(value) and COORD_MIN <= value <= COORD_MAX


def cross(ax, ay, bx, by, cx, cy) -> int:
    """(B-A) x (C-A), 整数运算。"""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _validate_vertex(value):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not _coord_ok(value[0])
        or not _coord_ok(value[1])
    ):
        raise ValidationError(
            "门的顶点必须是 2 个整数坐标 (size,intensity), 且坐标在 0~1000 之间"
        )
    return (value[0], value[1])


def _normalized_polygon(vertices):
    """校验顶点不重复、个数合法、按环向排列、凸、非零面积。

    返回 (顶点列表(按原环向), orientation): orientation 为 1 表示逆时针,
    -1 表示顺时针。允许连续共线顶点(cross==0), 但多边形整体面积必须非零。
    """
    if not isinstance(vertices, list):
        raise ValidationError("多边形门的 vertices 必须是顶点数组")
    if not (MIN_VERTICES <= len(vertices) <= MAX_VERTICES):
        raise ValidationError(
            f"凸多边形门需要 {MIN_VERTICES}~{MAX_VERTICES} 个顶点"
        )

    seen = set()
    pts = []
    for raw in vertices:
        v = _validate_vertex(raw)
        if v in seen:
            raise ValidationError("多边形门的顶点不得重复")
        seen.add(v)
        pts.append(v)

    n = len(pts)
    signs = set()
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        cx, cy = pts[(i + 2) % n]
        c = cross(ax, ay, bx, by, cx, cy)
        if c != 0:
            signs.add(1 if c > 0 else -1)

    if not signs:
        raise ValidationError("多边形门面积为零: 所有顶点共线")
    if len(signs) > 1:
        raise ValidationError("多边形门必须是按环向排列的凸多边形")

    orientation = next(iter(signs))
    return pts, orientation


def _on_segment(px, py, ax, ay, bx, by) -> bool:
    if cross(ax, ay, bx, by, px, py) != 0:
        return False
    return (
        min(ax, bx) <= px <= max(ax, bx)
        and min(ay, by) <= py <= max(ay, by)
    )


def _point_in_polygon(point: Point, vertices, orientation) -> bool:
    """凸多边形命中判定, 边界点算命中。

    对环向上每条有向边, 内部点都位于同一侧(cross 与 orientation 同号),
    在边上(on_segment)同样算命中。全程整数运算, 无浮点误差。
    """
    px, py = point.size, point.intensity
    n = len(vertices)
    for i in range(n):
        ax, ay = vertices[i]
        bx, by = vertices[(i + 1) % n]
        c = cross(ax, ay, bx, by, px, py)
        if c == 0:
            if _on_segment(px, py, ax, ay, bx, by):
                return True
            # 与该边支撑线共线但不在此子段上: 可能落在下一条共线子段上
            # (允许连续共线顶点), 不能立即判外, 交给其余边判定。
            continue
        if c > 0 and orientation < 0:
            return False
        if c < 0 and orientation > 0:
            return False
    return True


def _validate_top_keys(payload):
    if not isinstance(payload, dict):
        raise ValidationError("请求体必须是 JSON 对象")
    extra = set(payload) - _TOP_KEYS
    if extra:
        raise ValidationError(f"请求体包含未知字段: {sorted(extra)}")
    missing = _TOP_KEYS - set(payload)
    if missing:
        raise ValidationError(f"请求体缺少必需字段: {sorted(missing)}")
    if not isinstance(payload["points"], list):
        raise ValidationError("points 必须是数组")
    if not isinstance(payload["gates"], list):
        raise ValidationError("gates 必须是数组")
    if len(payload["points"]) > MAX_POINTS:
        raise ValidationError(f"点的数量不得超过 {MAX_POINTS}")
    if len(payload["gates"]) > MAX_GATES:
        raise ValidationError(f"门的数量不得超过 {MAX_GATES}")


def _validate_points(raw_points):
    points = []
    ids = set()
    for raw in raw_points:
        if not isinstance(raw, dict):
            raise ValidationError("每个点必须是对象")
        if set(raw) != _POINT_KEYS:
            extra = set(raw) - _POINT_KEYS
            if extra:
                raise ValidationError(f"点包含未知字段: {sorted(extra)}")
            raise ValidationError("点缺少必需字段 id/size/intensity")
        pid, size, intensity = raw["id"], raw["size"], raw["intensity"]
        if not _is_int(pid):
            raise ValidationError("点 id 必须是整数(不允许布尔值)")
        if pid in ids:
            raise ValidationError(f"点 id 重复: {pid}")
        if not _coord_ok(size) or not _coord_ok(intensity):
            raise ValidationError("点的 size/intensity 必须是 0~1000 的整数")
        ids.add(pid)
        points.append(Point(id=pid, size=size, intensity=intensity))
    return points


def _validate_gate_header(raw, index, seen_ids):
    if not isinstance(raw, dict):
        raise ValidationError(f"第 {index + 1} 个门必须是对象")
    # polygon/combine 允许的键集合不同, 此处先对两类键的并集做拦截,
    # 后续按类型再精确核对多余/缺失字段。
    unknown = set(raw) - (_POLYGON_KEYS | _COMBINE_KEYS)
    if unknown:
        raise ValidationError(
            f"第 {index + 1} 个门包含未知字段: {sorted(unknown)}"
        )
    missing = _GATE_KEYS - set(raw)
    if missing:
        raise ValidationError(
            f"第 {index + 1} 个门缺少必需字段: {sorted(missing)}"
        )
    gid = raw["id"]
    if not isinstance(gid, str) or not gid or len(gid) > 64:
        raise ValidationError(
            f"第 {index + 1} 个门的 id 必须是 1~64 字符的非空字符串"
        )
    if gid in seen_ids:
        raise ValidationError(f"门 id 重复: {gid}")
    gtype = raw["type"]
    if gtype not in GATE_TYPES:
        raise ValidationError(
            f"门 {gid} 的 type 未知: {gtype!r}(仅支持 polygon/combine)"
        )
    return gid, gtype


def _apply_op(op, left: set, right: set) -> set:
    if op == "AND":
        return left & right
    if op == "OR":
        return left | right
    return left - right  # DIFF


def evaluate(payload: dict) -> dict:
    """校验并计算所有门。成功时构造响应, 失败抛 ValidationError。"""
    _validate_top_keys(payload)
    points = _validate_points(payload["points"])

    # 每点按门顺序的命中向量; 先做空门定义校验, 再统一填值。
    vectors: dict[int, list[int]] = {p.id: [] for p in points}
    gate_results: list[dict] = []
    sets: dict[str, set] = {}

    for index, raw in enumerate(payload["gates"]):
        gid, gtype = _validate_gate_header(raw, index, sets)

        if gtype == "polygon":
            if set(raw) != _POLYGON_KEYS:
                extra = set(raw) - _POLYGON_KEYS
                if extra:
                    raise ValidationError(f"门 {gid} 包含未知字段: {sorted(extra)}")
                raise ValidationError(f"多边形门 {gid} 缺少 vertices 字段")
            vertices, orientation = _normalized_polygon(raw["vertices"])
            hit = {
                p.id
                for p in points
                if _point_in_polygon(p, vertices, orientation)
            }
            gate_def = {"vertices": [list(v) for v in vertices]}
        else:
            if set(raw) != _COMBINE_KEYS:
                extra = set(raw) - _COMBINE_KEYS
                if extra:
                    raise ValidationError(f"门 {gid} 包含未知字段: {sorted(extra)}")
                raise ValidationError(
                    f"组合门 {gid} 需要且仅需要 op/left/right 字段"
                )
            op = raw["op"]
            if op not in VALID_OPS:
                raise ValidationError(
                    f"组合门 {gid} 的 op 必须是 AND/OR/DIFF, 得到 {op!r}"
                )
            for side in ("left", "right"):
                ref = raw[side]
                if not isinstance(ref, str) or not ref:
                    raise ValidationError(
                        f"组合门 {gid} 的 {side} 必须是已定义门的 id 字符串"
                    )
                if ref not in sets:
                    raise ValidationError(
                        f"组合门 {gid} 引用了未知或更早之前未定义的门: {ref}"
                    )
            hit = _apply_op(op, sets[raw["left"]], sets[raw["right"]])
            gate_def = {"op": op, "left": raw["left"], "right": raw["right"]}

        sets[gid] = hit
        sorted_ids = sorted(hit)
        for pid in vectors:
            vectors[pid].append(1 if pid in hit else 0)
        gate_results.append(
            {
                "id": gid,
                "type": gtype,
                "count": len(sorted_ids),
                "hitIds": sorted_ids,
                **gate_def,
            }
        )

    sorted_points = sorted(points, key=lambda p: p.id)
    return {
        "points": [
            {"id": p.id, "size": p.size, "intensity": p.intensity}
            for p in sorted_points
        ],
        "gates": gate_results,
        "vectors": [
            {"id": p.id, "hits": vectors[p.id]} for p in sorted_points
        ],
    }
