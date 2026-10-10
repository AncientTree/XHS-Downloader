import sqlite3
import json
import os
from pathlib import Path

# --- 配置 ---
JSONL_FILE = Path("sync_data.jsonl")
DB_FILE = Path("sync_data.db")

def migrate():
    # 1. 检查源文件
    if not JSONL_FILE.exists():
        print(f"❌ 错误：找不到源文件 {JSONL_FILE}")
        return

    print(f"正在准备将 {JSONL_FILE} 迁移至 {DB_FILE} ...")

    # 2. 连接数据库（如果不存在会自动创建）
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 3. 确保表结构存在 (保持与 app.py 一致)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            json_content TEXT,
            synced INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # 4. 读取并插入数据
    success_count = 0
    skip_count = 0
    error_count = 0

    try:
        with open(JSONL_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    
                    # 获取关键字段
                    note_id = data.get("作品ID")
                    # JSON中的 true/false 转为 SQLite 的 1/0
                    is_synced_bool = data.get("synced", False)
                    is_synced_int = 1 if is_synced_bool else 0

                    if not note_id:
                        print(f"⚠️ 第 {line_num} 行跳过：缺少'作品ID'")
                        skip_count += 1
                        continue

                    # 插入数据 (INSERT OR IGNORE 会自动跳过已存在的 ID)
                    # 我们直接把读取到的整行 JSON 字符串存入 json_content
                    cursor.execute(
                        "INSERT OR IGNORE INTO notes (note_id, json_content, synced) VALUES (?, ?, ?)",
                        (note_id, line, is_synced_int)
                    )
                    
                    #通过 rowcount 判断是否真的插入了数据（如果是重复数据，rowcount为0）
                    if cursor.rowcount > 0:
                        success_count += 1
                    else:
                        skip_count += 1 # ID 已存在

                except json.JSONDecodeError:
                    print(f"⚠️ 第 {line_num} 行跳过：JSON 格式错误")
                    error_count += 1
                except Exception as e:
                    print(f"⚠️ 第 {line_num} 行发生未知错误: {e}")
                    error_count += 1

        # 5. 提交事务
        conn.commit()
        
        print("-" * 30)
        print("✅ 迁移完成！")
        print(f"📥 成功插入: {success_count} 条")
        print(f"⏭️ 重复跳过: {skip_count} 条")
        print(f"❌ 格式错误: {error_count} 条")
        print("-" * 30)

        # 6. 验证数据库当前状态
        cursor.execute("SELECT COUNT(*) FROM notes WHERE synced = 0")
        unsynced = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM notes")
        total = cursor.fetchone()[0]
        
        print(f"📊 数据库当前状态: 总计 {total} 条，未同步 {unsynced} 条")

    except Exception as e:
        print(f"❌ 发生致命错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()