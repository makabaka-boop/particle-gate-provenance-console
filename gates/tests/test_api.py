"""HTTP 层测试: 422/400 映射与正常响应结构。"""

import json

from app import create_app


def _client():
    return create_app().test_client()


TRIANGLE_CASE = {
    "points": [
        {"id": 3, "size": 5, "intensity": 5},
        {"id": 1, "size": 50, "intensity": 50},
        {"id": 2, "size": 0, "intensity": 0},
    ],
    "gates": [
        {"id": "big", "type": "polygon",
         "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        {"id": "combo", "type": "combine",
         "op": "AND", "left": "big", "right": "big"},
    ],
}


def test_healthz():
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_evaluate_ok_sorting_and_structure():
    resp = _client().post("/api/evaluate", json=TRIANGLE_CASE)
    assert resp.status_code == 200
    data = resp.get_json()
    # 点与命中 id 都按 id 排序
    assert [p["id"] for p in data["points"]] == [1, 2, 3]
    big = data["gates"][0]
    assert big["id"] == "big"
    assert big["type"] == "polygon"
    assert big["hitIds"] == [2, 3]
    assert big["count"] == 2
    combo = data["gates"][1]
    assert combo["hitIds"] == [2, 3]
    assert combo["left"] == "big" and combo["right"] == "big"
    # 向量逐点、按门顺序
    vecs = {v["id"]: v["hits"] for v in data["vectors"]}
    assert vecs[1] == [0, 0]
    assert vecs[2] == [1, 1]
    assert vecs[3] == [1, 1]


def test_422_on_forward_reference():
    payload = {
        "points": [],
        "gates": [
            {"id": "c", "type": "combine", "op": "AND",
             "left": "a", "right": "a"},
            {"id": "a", "type": "polygon",
             "vertices": [[0, 0], [1, 0], [1, 1]]},
        ],
    }
    resp = _client().post("/api/evaluate", json=payload)
    assert resp.status_code == 422
    assert "error" in resp.get_json()


def test_422_on_extra_field():
    payload = {"points": [], "gates": [], "nope": True}
    resp = _client().post("/api/evaluate", json=payload)
    assert resp.status_code == 422


def test_400_on_malformed_json():
    resp = _client().post(
        "/api/evaluate",
        data="{not json",
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_422_on_non_object_body():
    resp = _client().post("/api/evaluate", json=[1, 2, 3])
    assert resp.status_code == 422


def test_empty_case_ok():
    resp = _client().post("/api/evaluate", json={"points": [], "gates": []})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"points": [], "gates": [], "vectors": []}
