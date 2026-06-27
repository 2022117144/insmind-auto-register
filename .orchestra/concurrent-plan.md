# 并发生成 + 批量注册 改造方案

## 问题
1. **账号选号竞态**: 两个并发请求同时 SELECT，拿到同一个账号，分别去生成 → 浪费一个，另一个失败
2. **注册串行**: 一次只能注册一个
3. **生成同步等 SSE**: 前端卡住直到视频生成完毕

## 改造方案

### 1. 账号原子锁（防竞态）
选中账号后立即 UPDATE status='generating'，其他请求再查询时自动跳过。生成完成后：
- 成功 → DELETE
- 失败 → 恢复 status='active'（可重试）

### 2. 批量注册
新端点 `POST /api/insmind/accounts/auto-register-batch?count=N`
- 并发启动 N 个 register_insmind.py 子进程
- 限制最大 5 并发（Playwright 吃资源）
- 收集结果批量返回

### 3. 并发生成
- 无需改 insmind2api（每个 SSE 请求独立）
- 只需后端事务锁 + 前端可同时发多个请求