/**
 * 调用 gates 服务, 支持 AbortSignal。
 * 422/400 与网络错误统一抛出带 message 的 Error。
 */
export async function evaluateGates(payload, signal) {
  let resp
  try {
    resp = await fetch('/api/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error(`无法连接计算服务: ${err.message}`)
  }

  let data = null
  try {
    data = await resp.json()
  } catch {
    /* 非 JSON 响应留到状态码分支处理 */
  }

  if (!resp.ok) {
    throw new Error(
      data && data.error
        ? `${resp.status}: ${data.error}`
        : `计算服务返回 ${resp.status}`,
    )
  }
  return data
}
