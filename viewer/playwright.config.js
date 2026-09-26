import { defineConfig, devices } from '@playwright/test'

// 浏览器流程: 前端经 Vite 代理(/api -> localhost:5000)连接 gates 服务。
// 先启动: (cd gates && flask --app app run --port 5000) 与 npm run dev。
export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.VIEWER_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // 容器/无显卡 ARM 环境下提升 headless-shell 稳定性。
        launchOptions: {
          args: ['--disable-gpu', '--disable-dev-shm-usage', '--no-zygote'],
        },
      },
    },
  ],
  webServer: process.env.VIEWER_URL
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://localhost:5173',
        reuseExistingServer: true,
        timeout: 30000,
      },
})
