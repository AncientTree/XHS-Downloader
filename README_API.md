# XHS-Downloader API 文档（定制服务器版）

> 本文档描述本服务器**对外暴露的 HTTP API** 的设计与用法，供维护与二次开发参考。
> 与上游项目的关系、程序运行方式等通用说明见 [README.md](./README.md)。

---

## 1. 服务定位

本服务基于开源项目 [XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) 定制，作用是在**客户端之间中转小红书笔记数据**：

```
iPhone 客户端 ──POST /xhs/detail──▶ 服务器抓取笔记 ──▶ 写入数据库（synced=0）
                                                          │
PC 客户端 ──GET /sync/status──▶ 比对哈希，发现变化 ──GET /sync/data──▶ 取回待同步笔记
                                                          │
PC 客户端自行下载文件 ──POST /sync/commit_one──▶ 标记笔记已同步（synced=1）
```

**核心约定：服务器只存储笔记的 JSON 数据（含下载地址 URL），不负责下载文件。** 文件下载由各客户端自行完成。

---

## 2. 运行与部署

| 项目 | 说明 |
| --- | --- |
| 启动入口 | `run_api.py`（`systemd` 服务 `xhs-downloader.service` 拉起） |
| 监听地址 | `0.0.0.0:8000`（所有网卡，含公网） |
| Cookie | 读取项目根目录 `cookies.txt` 的**第一行**，用于请求小红书接口 |
| 数据存储 | SQLite：`sync_data.db`（表 `notes`） |
| 交互式文档 | 启动后可访问 `http://<host>:8000/docs`（Swagger UI）、`/redoc` |
| 运行用户 | `root`（见 service 文件） |

> ⚠️ 服务绑定 `0.0.0.0` 且 **`/sync/*` 接口无鉴权**，请勿将端口直接暴露公网，或在前面加反向代理做访问控制。

---

## 3. 接口总览

| 方法 | 路径 | 作用 | 鉴权 |
| --- | --- | --- | --- |
| `GET` | `/` | 跳转至项目 GitHub 仓库 | 无 |
| `POST` | `/xhs/detail` | 抓取小红书作品数据；**成功即写入待同步队列** | 无 |
| `GET` | `/sync/status` | 获取当前同步状态（哈希 + 未同步数量） | 无 |
| `GET` | `/sync/data` | 获取所有未同步的笔记数据 | 无 |
| `POST` | `/sync/commit_one` | 将单条笔记标记为已同步 | 无 |

所有接口返回 **JSON**（`/` 除外，为 307 重定向）。

---

## 4. 接口详情

### 4.1 `POST /xhs/detail` —— 抓取作品数据并入库

本服务最主要的写入入口。抓取成功后，笔记会被写入 `notes` 表（`synced=0`），供其他客户端同步。

**请求体**（`application/json`）：

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | string | ✅ | — | 小红书作品链接，自动提取；**不支持多链接** |
| `download` | bool | ❌ | `false` | 是否在服务器端下载文件。本定制场景应保持 `false`（只存 URL） |
| `index` | list[int\|str] | ❌ | `null` | 指定的图片序号，仅图文作品且 `download=true` 时生效 |
| `cookie` | string | ❌ | 配置文件 | 覆盖默认 Cookie |
| `proxy` | string | ❌ | 配置文件 | 本次请求使用的代理 |
| `skip` | bool | ❌ | `false` | `true` 时若作品已有下载记录则跳过 |

**支持链接格式**：

- `https://www.xiaohongshu.com/explore/<作品ID>?xsec_token=...`
- `https://www.xiaohongshu.com/discovery/item/<作品ID>?xsec_token=...`
- `https://www.xiaohongshu.com/user/profile/<作者ID>/<作品ID>?...`
- 短链：`https://xhslink.com/...`、`https://xhslink.cn/...`、`https://xhslink.com.cn/...`

**响应体**：

```jsonc
{
  "message": "获取小红书作品数据成功",
  "params": { "url": "...", "download": false, "index": null, "cookie": null, "proxy": null, "skip": false },
  "data": { /* 笔记数据对象，见第 6 节；失败时为 null */ }
}
```

**示例**：

```bash
curl -X POST http://127.0.0.1:8000/xhs/detail \
  -H "Content-Type: application/json" \
  -d '{"url": "https://xhslink.cn/o/1cSW86iXKdO"}'
```

> ⚠️ **副作用**：每次成功的调用都会向数据库写入一条记录（`INSERT OR IGNORE` 按作品 ID 去重）。因此"测试接口"本身即会产生真实待同步数据。

---

### 4.2 `GET /sync/status` —— 获取同步状态

供客户端**廉价轮询**：只需比对哈希是否变化，无需拉取全量数据。

**响应体**：

```jsonc
{
  "hash": "e5d1655b412470166840d61e2366e758",
  "unsynced_count": 36
}
```

- `hash`：所有**未同步**笔记 ID 排序拼接后的 MD5；无未同步数据时为字符串 `"all_synced"`。
- `unsynced_count`：未同步笔记数量。

> 客户端逻辑：本地保存上次的 `hash`，与本次结果不一致时才调用 `/sync/data`。

---

### 4.3 `GET /sync/data` —— 获取未同步笔记

返回所有 `synced=0` 的笔记。

**响应体**：JSON **数组**，元素为笔记数据对象（结构见第 6 节）。

```jsonc
[
  { "作品ID": "6a32745a0000000011011cc4", "作品标题": "...", "下载地址": ["https://ci.xiaohongshu.com/..."], "synced": false },
  { "作品ID": "...", "...": "..." }
]
```

> 注意：接口返回的是 `notes.json_content` 中存储的原始 JSON（数组元素内**含** `作品ID` 字段，客户端据此提交 `commit_one`）。

---

### 4.4 `POST /sync/commit_one` —— 标记单条已同步

客户端**下载完某条笔记的文件后**调用。逐条提交，避免批量失败导致状态不一致。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `note_id` | string | ✅ | 作品 ID（对应笔记数据中的 `作品ID`） |

**响应体**：

```jsonc
{
  "message": "success",
  "new_status": { "hash": "829b1d14099cb52dd7bf95cc509c8dc9", "unsynced_count": 24 }
}
```

> 提交后该笔记 `synced` 置为 `1`，之后 `GET /sync/data` 不再返回它（`json_content` 内的 `synced` 字段**不会**同步更新，以数据库字段为准）。

---

### 4.5 `GET /` —— 仓库跳转

返回 `307` 重定向至项目 GitHub 仓库地址。

---

## 5. 客户端同步流程（时序）

```
iPhone                                   服务器                            PC 客户端
  │  POST /xhs/detail {url}                │                                  │
  ├───────────────────────────────────────▶│  抓取笔记                        │
  │                                        │  INSERT notes(synced=0)          │
  │◀───────────────────────────────────────┤  返回笔记 JSON                   │
  │                                        │                                  │
  │                                        │◀── GET /sync/status ─────────────┤
  │                                        ├─── {hash, unsynced_count} ──────▶│ 比对 hash
  │                                        │                                  │
  │                                        │◀── GET /sync/data ───────────────┤ hash 变化时
  │                                        ├─── [未同步笔记数组] ─────────────▶│
  │                                        │                                  │ 按 下载地址 自行下载
  │                                        │◀── POST /sync/commit_one ────────┤ 逐条提交
  │                                        ├─── {new_status} ────────────────▶│
```

---

## 6. 数据模型

### 6.1 笔记数据对象字段

`/xhs/detail` 的 `data` 与 `/sync/data` 数组元素共用同一结构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `作品ID` | string | 笔记唯一 ID，**同步/提交的主键** |
| `作品链接` | string | 标准 `explore/` 链接 |
| `作品标题` | string | 标题 |
| `作品描述` | string | 正文 |
| `作品类型` | string | `图文` / `图集` / `视频` |
| `作品标签` | string | 标签（空格分隔） |
| `发布时间` / `最后更新时间` | string | 格式 `YYYY-MM-DD_HH:MM:SS` |
| `时间戳` | float | 发布时间戳 |
| `收藏数量` / `评论数量` / `分享数量` / `点赞数量` | string | 互动数据（可能含"万"等中文单位） |
| `作者昵称` / `作者ID` / `作者链接` | string | 作者信息 |
| `下载地址` | list[string] | **无水印文件直链**（图文为图片、视频为 mp4） |
| `动图地址` | list[string\|null] | live photo 动图直链，无则为 `null` |
| `synced` | bool | 入库时写入 `false`；仅作标记，**以数据库列为准** |

### 6.2 数据库结构

```sql
CREATE TABLE notes (
    note_id     TEXT PRIMARY KEY,          -- 作品ID
    json_content TEXT,                     -- 完整笔记 JSON 字符串
    synced      INTEGER DEFAULT 0,         -- 0=待同步, 1=已同步
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. 维护须知

- **无鉴权**：`/sync/*` 与 `/xhs/detail` 均无任何认证。若端口对公网开放，任何人都能拉取全部笔记数据（含文件直链）或写入数据。建议加反向代理 + Token 校验，或限制来源 IP。
- **相对路径**：`sync_data.db` 等路径为相对路径，依赖进程工作目录。systemd 服务已设 `WorkingDirectory=/root/App/XHS-Downloader`；若手动从其他目录启动，会生成新的空库。
- **写入即入库**：`/xhs/detail` 成功即写库，测试会污染真实数据。需要"只读查询"能力时应另行设计。
- **短链域名**：正则见 `source/application/app.py` 中的 `SHORT`，已支持 `xhslink.com` / `xhslink.cn` / `xhslink.com.cn`；如遇新域名需同步扩展。
- **网络依赖**：抓取依赖服务器到 `xhslink.cn`（腾讯云 CDN）及 `xiaohongshu.com` 的出网连通性。服务器上存在代理栈（sing-box / xray / Cloudflare WARP），代理波动会导致 `ConnectTimeout` —— 相关日志形如 `网络异常，<url> 请求失败: ConnectTimeout('')`。
- **重试行为**：抓取失败时按固定间隔多次重试，若上游长时间不可达，客户端可能先超时。排查时优先确认服务器出网，而非客户端。
- **迁移脚本**：`migrate_jsonl_to_sqlite.py` 为历史 JSONL → SQLite 的一次性迁移工具，保留备查。

---

*文档随接口变更同步更新；变更接口时请一并修改本文件。*
