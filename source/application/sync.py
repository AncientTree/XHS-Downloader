"""
同步功能模块（SQLite 版）

用于在多个客户端之间中转小红书笔记数据：
- `/xhs/detail` 抓取成功后调用 ``append_to_sync_file()`` 将笔记写入待同步队列；
- `/sync/status`、`/sync/data` 供客户端拉取未同步数据；
- `/sync/commit_one` 供客户端下载完成后标记已同步。

本模块独立于 ``app.py``，仅通过 :func:`register_sync_routes` 与
:func:`append_to_sync_file` 两个入口接入主程序，以尽量减少与上游的冲突。
"""

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 数据库文件路径（相对进程工作目录）
DB_FILE = Path("sync_data.db")


class CommitOneParams(BaseModel):
    note_id: str


def init_db() -> None:
    """初始化数据库表结构"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            json_content TEXT,
            synced INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def calculate_db_hash() -> str:
    """计算未同步笔记的哈希指纹（未同步 ID 排序拼接后取 MD5）"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT note_id FROM notes WHERE synced = 0 ORDER BY note_id")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return "all_synced"
    content = "".join(row[0] for row in rows)
    return hashlib.md5(content.encode()).hexdigest()


def get_unsynced_count() -> int:
    """获取未同步笔记数量"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM notes WHERE synced = 0")
    count = cursor.fetchone()[0]
    conn.close()
    return count


async def append_to_sync_file(data: dict) -> None:
    """将笔记写入待同步队列（异步包装，已存在则忽略）"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _insert_note_to_db, data)


def _insert_note_to_db(data: dict) -> None:
    """实际的数据库插入操作"""
    note_id = data.get("作品ID")
    if not note_id:
        return

    # 写入的 JSON 里保留一份 synced 字段，便于客户端直接读取
    data["synced"] = False
    json_str = json.dumps(data, ensure_ascii=False)

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # INSERT OR IGNORE: 作品 ID 已存在则不操作
        cursor.execute(
            "INSERT OR IGNORE INTO notes (note_id, json_content, synced) VALUES (?, ?, 0)",
            (note_id, json_str),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"数据库插入错误: {e}")


def register_sync_routes(server: FastAPI, logging=None) -> None:
    """将同步相关路由注册到 FastAPI 实例。

    :param server: FastAPI 应用实例
    :param logging: 可选的日志回调（如 XHS 实例的 logging 方法）
    """

    @server.get("/sync/status", summary="获取当前数据状态", tags=["Sync"])
    async def get_sync_status():
        """返回当前的哈希指纹和未同步数量"""
        return JSONResponse(
            content={
                "hash": calculate_db_hash(),
                "unsynced_count": get_unsynced_count(),
            }
        )

    @server.get("/sync/data", summary="获取所有未同步的笔记数据", tags=["Sync"])
    async def get_unsynced_data():
        """从数据库读取所有 synced=0 的记录"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # 允许按列名访问
        cursor = conn.cursor()
        cursor.execute("SELECT json_content FROM notes WHERE synced = 0")
        rows = cursor.fetchall()
        conn.close()

        # 解析 JSON 字符串返回列表
        data_list = []
        for row in rows:
            try:
                data_list.append(json.loads(row["json_content"]))
            except Exception:
                continue
        return JSONResponse(content=data_list)

    @server.post("/sync/commit_one", summary="标记单条笔记为已同步", tags=["Sync"])
    async def commit_one_sync(params: CommitOneParams):
        """将单条笔记标记为已同步，避免批量提交导致状态不一致"""
        note_id = params.note_id
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE notes SET synced = 1 WHERE note_id = ?", (note_id,))
        conn.commit()
        changes = conn.total_changes
        conn.close()

        if changes > 0 and logging:
            logging(f"笔记 {note_id} 已标记为同步 (SQLite).")

        return JSONResponse(
            content={
                "message": "success",
                "new_status": {
                    "hash": calculate_db_hash(),
                    "unsynced_count": get_unsynced_count(),
                },
            }
        )


# 模块加载时初始化数据库
init_db()
