# insMind 项目 handoff — V6.1

## 最后状态
- ✅ insmind2api 带日志运行（`logs/server.log`），PID 22740，5105 端口正常
- ✅ 5 个 insMind 账号在池，5105 池也有 5 个
- ✅ 前端模型过滤：Pixverse-V6.0、Seedance-2.0-Mini、Wan-2.2
- ✅ Pixverse-V6.0 固定 5s / 360p
- ✅ Wan-2.2 固定 5s / 480p
- ✅ Seedance-2.0-Mini 固定 5s / 480p

## 已知问题
- insmind2api 之前崩溃过（502 Bad Gateway），根因未知（旧启动方式 `DEVNULL` 吞了日志）
- 现在日志已开启，下次崩溃可以查 `insmind2api/logs/server.log`
- 启动方式改为 `node dist/index.js >> logs/server.log 2>&1`
- `starter.py` 已更新为带日志启动
- 生成视频超过 4 分钟仍会返回 `processing`，前端显示"生成中"
- 注册的 insMind 账号积分都是 0（需要确认是否影响生成）

## 关键决策
- 轮询 8 次 × 30 秒 = 4 分钟，超时后返回 `processing`
- 每次生成成功自动删除账号（从 DB 和池中移除）
- 生成中账号状态设为 `generating`，完成后释放为 `active`
- 5105 日志写入 `logs/server.log`，不再用 DEVNULL