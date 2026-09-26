"""Flask 计算服务: 只暴露 /healthz 与 /api/evaluate。"""

from __future__ import annotations

from flask import Flask, jsonify, request

from .gates import ValidationError, evaluate


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.post("/api/evaluate")
    def api_evaluate():
        # silent=True 让畸形 JSON 返回 None, 统一报 400(语法层),
        # 而字段/语义错误一律 422。
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify(error="请求体必须是合法的 JSON 对象"), 400
        try:
            result = evaluate(payload)
        except ValidationError as exc:
            return jsonify(error=str(exc)), 422
        return jsonify(result)

    return app


app = create_app()
