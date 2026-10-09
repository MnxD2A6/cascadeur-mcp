# 实用示例与能力边界 / Practical use cases

当前版本是 **0.5.0a13 Alpha**。它让 Agent 通过结构化工具读取和编辑
Cascadeur 中的动画；动作设计、视觉质量和参考视频复刻不是连接成功的保证。
实机验证仅在开发者本机 Windows / Cascadeur 2026.2.2 上完成。

## 适合用来做什么

| 工作 | 当前支持范围 |
|---|---|
| 检查角色 | 读取真实骨架、Cascy 语义映射、姿势和轨道信息 |
| 批量编辑 | 一次修改多个语义 Point 控制组及多个现有帧 |
| 修正已有动作 | 在支持的现有关键帧上偏移控制组并保留曲线元数据 |
| 调整 timing | 对支持的同步角色关键帧进行有界 retiming |
| 调整手指 | 使用专门的手指局部旋转接口；移动手部 Point 不会自动握拳 |
| 检查和恢复 | 读取实际解算结果、检查 snapshot/transaction 容量、验证恢复 |
| 保存和交付 | 保存新的场景副本；具备导出许可时导出完整支持角色的 FBX |

## 一个完整的已有动画修正示例

目标：在独立 Cascy 场景副本中，微调几个已有关键帧的右手位置，检查结果，
然后决定保留还是恢复。这是操作示例，不是已完成动画素材；仓库不附带角色或场景。

### 1. 安装并明确启用工具

先按 [试用指南](TRY_IT.md) 安装、连接。`examples/codex.toml` 默认只启用
三个只读工具，不能直接执行下面的编辑流程。按需修改同一个 MCP 配置表的
`enabled_tools`，保留其他配置。这个示例需要：

```toml
enabled_tools = [
  "ping_cascadeur", "get_scene_info", "list_characters",
  "get_bridge_capabilities", "get_recovery_status", "get_rig_semantics",
  "inspect_character_motion", "get_semantic_pose_sequence",
  "get_character_edit_readiness", "save_scene_copy",
  "offset_semantic_pose_sequence_preserving_curves", "restore_pose_snapshot",
  "play_animation", "stop_animation"
]
```

重连 MCP 后，让 Agent 检查实际工具签名和 host capability；工具列表出现不代表
当前 host、角色、轨道或目标位置已通过检查。客户端超时后不要自动重试写入。

### 2. 发现身份并保存独立副本

调用 `get_bridge_capabilities()`、`ping_cascadeur()`、`get_scene_info()` 和
`list_characters()`。客户端与 host 必须匹配 write-contract revision **3**。
保存新副本前确认没有外部播放：

```text
save_scene_copy(scene_id=<当前发现的 ID>, destination=<新的绝对 .casc 路径>)
```

这是签名说明，不是可直接执行的代码。目的路径必须不存在。
Save As 可以改变场景 ID；保存后重新发现 scene/character ID，不使用旧 snapshot ID。
调用 `get_recovery_status()`，如果写入仍被阻止，按
[恢复保护说明](PERSISTENT_RECOVERY.md) 处理，不删除记录绕过检查。

### 3. 检查真实关键帧并读取原姿势

调用 `get_rig_semantics(character_id)` 和 `inspect_character_motion(character_id)`。
选择编辑轨道上实际存在的关键帧。下面的 `[6, 10, 13]` 仅是假设示例；
如果场景没有这些 key，请换成实际 frame indices，不能假设自动补 key。
所有示例 ID 占位符必须替换为当前会话真实发现的值。

工具：`get_semantic_pose_sequence`

```json
{
  "character_id": "<discovered character UUID>",
  "frames": [6, 10, 13],
  "roles": ["right_hand"],
  "include_joint_state": false
}
```

工具：`get_character_edit_readiness`

```json
{
  "scene_id": "<discovered scene ID>",
  "character_id": "<discovered character UUID>",
  "frames": [6, 10, 13],
  "operation": "offset_semantic_pose_sequence_preserving_curves",
  "roles": ["right_hand"]
}
```

只有前置检查通过后才继续；它是建议性检查，不保证目标可达或写入成功。

### 4. 一次批量修正

工具：`offset_semantic_pose_sequence_preserving_curves`

```json
{
  "scene_id": "<discovered scene ID>",
  "character_id": "<discovered character UUID>",
  "frames": [6, 10, 13],
  "offsets": {"right_hand": [-0.05, 0.0, 0.0]}
}
```

这个调用把右手整个 Point 控制组沿世界 X 轴移动 -0.05 **原生场景单位**，
不是米、局部坐标或关节角度。示例幅度不适用于所有模型，应先检查场景尺寸。
它用一个工具调用完成三帧编辑，并自动捕获恢复状态。

保留返回的 `snapshot_id`，检查 actual poses、solver adjustments 和 `edit_impact`。
曲线元数据保留不等于轨迹形状不变；未直接写入的部位也可能因 rig 解算而移动。
普通 `offset_semantic_pose_sequence` 会创建完整角色 key 并使用 LINEAR，不能替代
这个保留曲线的修正流程。具体拒绝条件见 [曲线编辑](CURVE_PRESERVING_EDITING.md)。

### 5. 回读、连续播放、接受或恢复

重新读取相同帧，再检查整个 clip 的原生连续播放。`play_animation` 使用
`scene_id`、`start_frame` 和 `end_frame`；范围来自真实场景，不能写死为 22。
确认播放停止后才能继续编辑。`stop_animation` 只停止 bridge 拥有的播放。

数据成功不等于动作好看：检查肩肘姿势、脚部支撑、碰撞方向和完整动作节奏。
如果不接受修改，在同一会话、同一场景、没有外部编辑的情况下恢复：

工具：`restore_pose_snapshot`

```json
{
  "scene_id": "<discovered scene ID>",
  "snapshot_id": "<snapshot ID returned by the successful edit>"
}
```

恢复后仍要回读。session snapshot 不跨重启；单 Pose JSON 也不是整个 clip 的备份。
如果接受结果，保存到另一个新的 `.casc` 路径，再重新发现身份。

可把以下请求直接交给 Agent：

> 在我当前的 Cascy 动画中做一次可恢复的小幅右手修正。先检查 host 版本和恢复状态，
> 保存独立场景副本并重新发现身份，读取真实轨道与关键帧，再检查编辑 readiness。
> 对选定的现有 keys 使用一次保留曲线的 batch offset，保留 snapshot，回读实际结果
> 并播放整个 clip。不要修改不支持的轨道；未知写入结果不要自动重试。最后报告
> 改动及解算耦合，把视觉结果留给我检查。

## 可选 FBX 交付

先启用并调用 `get_fbx_export_status`，确认当前原生导出许可。需要交付时再按
`tools/list` 中的 `export_fbx` 签名提供当前 scene/character ID、新的绝对 FBX 路径、
新的 `source_copy_path` 和四个 export options。当前只支持完整 stored range，
`start_frame=0`、`end_frame=frame_count-1`，animation/skeleton 均为 true。
导出会先保存新原生副本并可能改变 scene ID；覆盖 FBX 必须提供原文件 SHA-256。
这不包含通用 Unity 导入工具或已打包的游戏工程。

## 当前明确不能承诺的事

- 从参考视频自动提取三维动作或一比一复刻：没有内置视频动捕后端。
- 一句话自动生成专业动画：semantic controls 提供执行接口，不保证设计质量。
- 任意 rig：目前验证的是 Cascy profile，不能把映射直接用于其他角色。
- 生产级无故障恢复：native shutdown crash 未解决，持久恢复锁不覆盖所有突然中断。
- 自动操作 AutoPhysics/AutoPosing、完整游戏系统或通用 Unity pipeline。
- 其他机器的 host connection：尚未验证；云端 Python CI 不替代 Cascadeur 实机测试。

普通 pose sequence 为 1–8 个现有帧；显式完整 sampled motion 最多 64 帧，
有额外范围和完整控制组要求，见 [sampled motion](SAMPLED_MOTION.md)。
项目、Cascadeur、模型和外部动捕服务分别遵循自己的许可。
