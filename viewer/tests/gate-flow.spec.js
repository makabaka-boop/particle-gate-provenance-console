// @ts-check
import { expect, test } from '@playwright/test'

/**
 * 一条完整浏览器流程:
 *  1. 计算 -> 散点与门控表的 data-response-id 相同(共享同一响应),
 *     且门控表计数、散点命中向量都与网络返回的那份 JSON 对得上;
 *  2. 选组合门 -> 散点金色命中数 == 门控表 count == 详情 id 数,
 *     两个输入门在表中置为输入行、在图中画出绿色多边形;
 *  3. 编辑后重新计算 -> 两侧 response id 一起递增;
 *  4. 逆向引用 -> 整次 422, 错误条出现;
 *  5. 旧请求不得覆盖新编辑: 首个请求被拖慢并在途中 abort,
 *     最终画面只反映第二次编辑的响应。
 */
test('散点与门控表共享同一响应, 高亮/编辑/422/竞态全流程', async ({ page }) => {
  await page.goto('/')

  // ---- 1. 首次计算, 抓网络响应用作核对基准 ----
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith('/api/evaluate') && r.status() === 200,
  )
  await page.getByTestId('run').click()
  const response = await responsePromise
  const data = await response.json()

  await expect(page.getByTestId('status')).toContainText(
    `${data.points.length} 个点 · ${data.gates.length} 个门 · 响应 #1`,
  )

  const scatterId1 = await page.getByTestId('scatter').getAttribute('data-response-id')
  const tableId1 = await page.getByTestId('gate-table').getAttribute('data-response-id')
  expect(scatterId1).toBe('1')
  expect(tableId1).toBe(scatterId1) // 散点与门控表共享同一响应

  // 门控表每一行 count 与响应逐门一致
  const rows = page.locator('[data-testid="gate-table"] tbody tr')
  await expect(rows).toHaveCount(data.gates.length)
  for (let i = 0; i < data.gates.length; i++) {
    await expect(rows.nth(i).locator('[data-testid="gate-count"]')).toHaveText(
      String(data.gates[i].count),
    )
  }

  // 每个散点的命中向量 data-hit-vector 与响应 vectors(按 id)逐位一致
  const expectedVec = Object.fromEntries(data.vectors.map((v) => [v.id, v.hits.join('')]))
  const circles = page.locator('[data-testid="points-layer"] circle')
  await expect(circles).toHaveCount(data.points.length)
  const circleCount = await circles.count()
  for (let i = 0; i < circleCount; i++) {
    const c = circles.nth(i)
    const pid = Number(await c.getAttribute('data-point-id'))
    expect(await c.getAttribute('data-hit-vector')).toBe(expectedVec[pid])
  }

  // ---- 2. 选中组合门 overlap = AND(core, bright) ----
  const overlap = data.gates.find((g) => g.id === 'overlap')
  await page.locator('[data-gate-id="overlap"]').click()
  await expect(page.getByTestId('detail-id')).toHaveText('overlap')
  await expect(page.getByTestId('detail-count')).toHaveText(String(overlap.count))

  // 散点金色(选中门命中)数量 == 门控表 count
  await expect(page.locator('circle.hit-selected')).toHaveCount(overlap.count)

  // 详情列出的排序 id 与响应完全一致
  const detailIds = (await page.getByTestId('detail-ids').textContent())
    .split(/[,\s…]+/)
    .filter(Boolean)
    .map(Number)
  // 预览可能截断, 只在 <=40 时全量核对(示例集远小于 40)
  if (overlap.count <= 40) {
    expect(detailIds).toEqual(overlap.hitIds)
  }

  // 两个输入门在表中标记为输入行
  await expect(page.locator('[data-gate-id="core"].input-row')).toHaveCount(1)
  await expect(page.locator('[data-gate-id="bright"].input-row')).toHaveCount(1)

  // 图上: 无金色多边形(选中门是组合门), 但有两个绿色输入门多边形
  await expect(page.locator('polygon[fill="rgba(255,209,102,0.14)"]')).toHaveCount(0)
  await expect(page.locator('polygon[stroke="#4cc9a4"]')).toHaveCount(2)

  // 绿色点 = 输入门并集命中但未被 overlap 命中
  const unionOnly = new Set([
    ...data.gates.find((g) => g.id === 'core').hitIds,
    ...data.gates.find((g) => g.id === 'bright').hitIds,
  ])
  for (const id of overlap.hitIds) unionOnly.delete(id)
  await expect(page.locator('circle.hit-input')).toHaveCount(unionOnly.size)

  // 改选多边形门 core: 金色多边形 1 个, 无输入行
  await page.locator('[data-gate-id="core"]').click()
  await expect(page.locator('polygon[fill="rgba(255,209,102,0.14)"]')).toHaveCount(1)
  await expect(page.locator('circle.hit-selected')).toHaveCount(
    data.gates.find((g) => g.id === 'core').count,
  )
  await expect(page.locator('tr.input-row')).toHaveCount(0)

  // ---- 3. 编辑: 往 points 末尾追加一个点, 重新计算 ----
  const pointsText = await page.getByTestId('points-input').inputValue()
  const points = JSON.parse(pointsText)
  points.push({ id: 999, size: 400, intensity: 460 }) // 位于 core 内部
  await page.getByTestId('points-input').fill(JSON.stringify(points))
  const resp2Promise = page.waitForResponse(
    (r) => r.url().endsWith('/api/evaluate') && r.status() === 200,
  )
  await page.getByTestId('run').click()
  const data2 = await (await resp2Promise).json()
  expect(data2.points.some((p) => p.id === 999)).toBe(true)

  // 散点与门控表的响应号同时推进到 2, 绝不允许一旧一新
  await expect(page.getByTestId('scatter')).toHaveAttribute('data-response-id', '2')
  await expect(page.getByTestId('gate-table')).toHaveAttribute('data-response-id', '2')
  await expect(circles).toHaveCount(data2.points.length)
  // 新点的命中向量与新响应一致
  const newVec = data2.vectors.find((v) => v.id === 999).hits.join('')
  await expect(page.locator('circle[data-point-id="999"]')).toHaveAttribute(
    'data-hit-vector',
    newVec,
  )

  // ---- 4. 逆向引用 -> 422, 错误条出现, 旧响应仍在 ----
  const gatesText = await page.getByTestId('gates-input').inputValue()
  const gatesJson = JSON.parse(gatesText)
  gatesJson.unshift({ id: 'future', type: 'combine', op: 'AND', left: 'core', right: 'nope' })
  await page.getByTestId('gates-input').fill(JSON.stringify(gatesJson))
  const resp422 = page.waitForResponse(
    (r) => r.url().endsWith('/api/evaluate') && r.status() === 422,
  )
  await page.getByTestId('run').click()
  await resp422
  await expect(page.getByTestId('error')).toBeVisible()
  await expect(page.getByTestId('error')).toContainText('422')
  // 旧结果未被清掉
  await expect(page.getByTestId('scatter')).toHaveAttribute('data-response-id', '2')
  await expect(page.getByTestId('gate-table')).toHaveAttribute('data-response-id', '2')

  // ---- 5. 竞态: 第一个请求拖慢, 编辑触发 abort, 第二个请求立即返回 ----
  // 恢复合法输入并加标记点 888, 作为"新编辑"的可观察内容
  const validPoints = data2.points
  validPoints.push({ id: 888, size: 400, intensity: 460 })
  await page.getByTestId('gates-input').fill(gatesText) // 恢复合法门
  let evaluateCall = 0
  await page.route('**/api/evaluate', async (route) => {
    evaluateCall += 1
    if (evaluateCall === 1) {
      await new Promise((r) => setTimeout(r, 1200)) // 旧请求拖慢
    }
    try {
      await route.continue()
    } catch {
      // 旧请求已被编辑动作 abort, continue 可能抛"请求已结束", 忽略。
    }
  })

  await page.getByTestId('points-input').fill(JSON.stringify(validPoints.slice(0, -1)))
  await page.getByTestId('run').click() // 第一次(慢), 点 888 不存在
  await page.waitForTimeout(250)
  await page.getByTestId('points-input').fill(JSON.stringify(validPoints)) // 编辑 -> abort
  await page.getByTestId('run').click() // 第二次(快), 含点 888

  // 最终画面: 点 888 存在; 旧响应若错误覆盖, 该点不会出现
  await expect(page.locator('circle[data-point-id="888"]')).toBeVisible({
    timeout: 10000,
  })
  await expect(page.getByTestId('error')).toBeHidden()
  // 散点与门控表仍共享同一个(最新)响应号
  const sid = await page.getByTestId('scatter').getAttribute('data-response-id')
  expect(await page.getByTestId('gate-table').getAttribute('data-response-id')).toBe(sid)
  await page.unroute('**/api/evaluate')
})
