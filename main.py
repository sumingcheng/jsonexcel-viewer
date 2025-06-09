import tempfile
import logging
import re
import os
from flask import Flask
from api import register_routes

# 设置日志 - 输出到控制台
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("token_analysis")

# 预编译正则表达式，避免重复编译
ETH_ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")
BTC_ADDRESS_PATTERN = re.compile(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}")

# 创建Flask应用
app = Flask(__name__)
# 使用固定的密钥，避免每次重启应用时会话失效
app.secret_key = "a_secure_random_secret_key_for_sessions"

# 配置临时文件夹
TEMP_FOLDER = tempfile.gettempdir()
os.makedirs(TEMP_FOLDER, exist_ok=True)

# 注册所有路由
register_routes(app, TEMP_FOLDER)

if __name__ == "__main__":
    logger.info("启动Token分析服务...")
    app.run(debug=True, host="0.0.0.0", port=23333)
