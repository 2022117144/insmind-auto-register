# insMind 项目 handoff — V6.0

## 最后状态
- ✅ insmind2api 轮询次数从 3 次改为 **8 次（4 分钟）**
- ✅ insmind2api 已重启（PTY 模式），5105 端口正常，8 个账号在池
- ✅ 前端模型过滤：Pixverse-V6.0、Seedance-2.0-Mini、Wan-2.2
- ✅ Pixverse-V6.0 固定 5s / 360p
- ✅ Wan-2.2 固定 5s / 480p
- ✅ Seedance-2.0-Mini 固定 5s / 480p

## 已知问题
- insmind2api 在非 PTY 模式下启动会立即退出（`stdin is not a tty`），需用 PTY 模式启动
- 旧进程残留端口 5105 时需先 kill
- 生成视频超过 4 分钟仍会返回 `processing`，前端显示"生成中"

## 关键决策
- 轮询 8 次 × 30 秒 = 4 分钟，超时后返回 `processing`
- 每次生成成功自动删除账号（从 DB 和池中移除）
- 生成中账号状态设为 `generating`，完成后释放为 `active`