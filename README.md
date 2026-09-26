# 颗粒检测仪 · 多级门控散点编辑

颗粒的两项读数 `(size, intensity)` 经过至多 20 道顺序门控。只看最终数量会
丢掉“某个颗粒在哪一道门被排除”的信息, 因此本系统返回每门命中的排序点 id、
命中数, 以及每个点**按门顺序的命中向量**。

- `gates/` — Python/Flask 计算服务(端口 5000), 纯整数叉积几何。
- `viewer/` — Vue 3 + Vite 散点编辑页; 生产环境由 nginx 托管并把 `/api`
  反代到 gates(容器内端口 8080, 宿主映射 8080)。
- `docker-compose.yml` — 分别启动 **viewer** 和 **gates** 两个服务。

## 一键启动(Compose)

```bash
docker compose up --build
# viewer: http://localhost:8080
# gates 直连(可选): http://localhost:5000/healthz
```

## 本地开发

```bash
# 计算服务
cd gates
pip install -r requirements-dev.txt
flask --app app run --port 5000

# 前端(自动把 /api 代理到 localhost:5000)
cd viewer
npm install
npm run dev        # http://localhost:5173
```

## 规则摘要(违反任意一条, 整次请求返回 422)

- 点: 至多 5000 个; `id` 为唯一整数; `size/intensity` 为 0~1000 整数。
- 门: 至多 20 个, **按数组顺序**定义, 门 id 为唯一非空字符串。
- 多边形门 `{"type":"polygon"}`: 3~12 个互不重复顶点, 按环向排列的凸多边形,
  非零面积; 允许边上存在连续共线顶点。**边界点算命中**(整数叉积, 无浮点误差)。
- 组合门 `{"type":"combine"}`: `op ∈ AND | OR | DIFF`, `left/right`
  只能引用**更早出现**的门(自引用/前向引用/未知门一律 422)。
  DIFF 为左集减右集。各门独立产生点集, 组合门做集合交/并/差。
- 任何层级的多余字段、缺失字段、类型错误、布尔值冒充整数等同样 422
  (畸形 JSON 为 400)。

## 响应结构 `POST /api/evaluate`

```jsonc
{
  "points": [{ "id": 3, "size": 5, "intensity": 5 } /* 按 id 排序 */],
  "gates": [
    { "id": "big", "type": "polygon", "count": 2,
      "hitIds": [2, 3] /* 排序后的命中点 id */,
      "vertices": [[0,0],[10,0],[10,10],[0,10]] },
    { "id": "x", "type": "combine", "op": "DIFF",
      "left": "big", "right": "other", "count": 1, "hitIds": [2] }
  ],
  // 每点一行, hits[i] 是该点对第 i 个门(按定义顺序)的 0/1 命中标记
  "vectors": [{ "id": 2, "hits": [1, 1] }, { "id": 3, "hits": [1, 0] }]
}
```

## 前端交互

- 左侧编辑 `points` / `gates` JSON, “计算门控”发请求; 编辑即标记为 stale
  并 **abort 在途请求**, 请求带单调序号, 迟到的旧响应一律丢弃
  (旧请求不得覆盖新编辑)。
- 点击右侧门控表任一门: 散点金色高亮该门命中的颗粒; 若是组合门,
  其两个输入门在表中置为输入行(绿色), 图中以绿色虚线多边形描出,
  仅输入门命中(而未被选中门命中)的点为绿色。
- 散点图与门控表渲染同一个响应对象, 两者 DOM 上都挂 `data-response-id`,
  供浏览器流程核对“散点和门控表共享同一响应”。

## 测试

```bash
# 后端: 独立射线法参照实现 vs 引擎半平面法, 60 个随机小点集对拍
# + 边界/共线/顺逆时针/AND/OR/DIFF/422/上限/HTTP 映射
cd gates && pytest          # 79 passed

# 一条浏览器流程(需 gates 在 5000; Playwright 会自动起 vite)
cd viewer && npx playwright test
```

浏览器流程依次核对: 两侧 `data-response-id` 相同且与网络 JSON 一致;
各门 count、每点命中向量对拍; 组合门高亮(金色数==count、两个输入门
多边形/输入行); 编辑后响应号同步递增; 逆向引用返回 422 且不污染旧结果;
慢请求途中被编辑 abort, 最终画面只反映第二次编辑(旧请求不覆盖新编辑)。
