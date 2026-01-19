#!/usr/bin/env python3
import asyncio
from source import XHS # 从项目的 source 包中导入 XHS 类
import os

# !!! --- 重要配置区 --- !!!
# 在这里填入你从浏览器获取的 Cookie
# 这是保证你能顺利抓取需要登录才能看到的内容的关键
cookies_file_path = 'cookies.txt'
XHS_COOKIE = "" 
if os.path.exists(cookies_file_path):
    with open(cookies_file_path, 'r', encoding='utf-8') as f:
        XHS_COOKIE = f.readline().strip() 
        # 将所有行合并成一个字符串
    print(f"成功读取的cookies字符串长度：{len(XHS_COOKIE)}")
else:
    print(f"错误：找不到文件 '{cookies_file_path}'。")
# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.

USER_Agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

# 其他可选配置
WORK_PATH = "." # 下载文件的保存路径，请替换为服务器上的实际路径
# !!! -------------------- !!!

async def main():
    """
    异步主函数，用于初始化和运行 API 服务器。
    """
    # 实例化 XHS 对象，传入你的配置
    # cookie 参数是关键
    async with XHS(cookie=XHS_COOKIE, work_path=WORK_PATH, user_agent=USER_Agent) as xhs:
        print("Starting FastAPI server...")
        # 调用 run_api_server 方法来启动服务器
        # 监听 0.0.0.0 表示允许来自任何 IP 的访问
        # 端口可以自定义，这里用 8000
        await xhs.run_api_server(host="0.0.0.0", port=8000)

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())