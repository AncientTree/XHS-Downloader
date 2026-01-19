#!/usr/bin/env python3
import json
import hashlib
import os
from pathlib import Path

# --- 配置 ---
EXPORT_FILE = Path("xhs_notes_export_1768806965.jsonl") # 您的导出文件名
SYNC_DATA_FILE = Path("sync_data.jsonl")
SYNC_STATUS_FILE = Path("sync_status.json")

def calculate_hash(file_path: Path) -> str:
    """计算文件的 SHA256 哈希值"""
    if not file_path.exists():
        return "no_data"
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def count_unsynced_items(file_path: Path) -> int:
    """实时计算文件中 'synced': false 的条目数量"""
    if not file_path.exists():
        return 0
    
    count = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
                if not item.get('synced', True):
                    count += 1
            except json.JSONDecodeError:
                continue
    return count

def read_sync_status() -> dict:
    """读取同步状态文件"""
    if not SYNC_STATUS_FILE.exists():
        return {"hash": "initial", "unsynced_count": 0}
    try:
        with open(SYNC_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"hash": "initial", "unsynced_count": 0}

def write_sync_status(status: dict):
    """写入同步状态文件"""
    with open(SYNC_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=4)

def main():
    if not EXPORT_FILE.exists():
        print(f"错误：找不到导出文件 {EXPORT_FILE}")
        return

    print(f"正在读取 {EXPORT_FILE} ...")
    
    added_count = 0
    
    # 1. 读取并追加写入
    with open(EXPORT_FILE, "r", encoding="utf-8") as f_in, \
         open(SYNC_DATA_FILE, "a", encoding="utf-8") as f_out:
        
        for line in f_in:
            line = line.strip()
            if not line: continue
            
            try:
                # 尝试解析以确保是有效的 JSON
                item = json.loads(line)
                
                # 确保 'synced' 字段为 false
                item['synced'] = False
                
                # 写入到 sync_data.jsonl
                f_out.write(json.dumps(item, ensure_ascii=False) + "\n")
                added_count += 1
                
            except json.JSONDecodeError as e:
                print(f"跳过无效行: {e}")
                continue

    print(f"成功向 {SYNC_DATA_FILE} 追加了 {added_count} 条记录。")

    # 2. 重新计算哈希和计数
    print("正在更新状态文件...")
    new_hash = calculate_hash(SYNC_DATA_FILE)
    
    # 这里我们直接重新计算整个文件的未同步数量，这是最准确的方法
    # 因为我们不仅要加上新增的，还要包含原本文件中可能存在的未同步条目
    total_unsynced = count_unsynced_items(SYNC_DATA_FILE)
    
    new_status = {
        "hash": new_hash,
        "unsynced_count": total_unsynced
    }
    
    write_sync_status(new_status)
    
    print(f"状态更新完成！")
    print(f"当前总哈希: {new_hash}")
    print(f"当前未同步总数: {total_unsynced}")

if __name__ == "__main__":
    main()