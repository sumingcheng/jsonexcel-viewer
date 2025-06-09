import pandas as pd
import json
import logging

# 获取logger
logger = logging.getLogger("token_analysis")


def parse_json_data(json_str):
    """解析JSON字符串并在失败时返回空字典"""
    if pd.isna(json_str) or not isinstance(json_str, str) or not json_str.strip():
        return {}

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {str(e)}, 原始字符串: {json_str[:100]}...")
        return {}
    except Exception as e:
        logger.error(f"解析JSON时发生未知错误: {str(e)}")
        return {}


def extract_tokens_and_addresses(row):
    """从JSON数据中提取Token和地址信息"""
    tokens = []
    addresses = []
    success = True

    if "xh_model" not in row or pd.isna(row["xh_model"]):
        return tokens, addresses, success

    try:
        xh_data = parse_json_data(row["xh_model"])
        if not xh_data:
            return tokens, addresses, success

        # 检查是否success为false
        if xh_data.get("success") is False:
            success = False
            return tokens, addresses, success

        # 从JSON数据中提取信息
        data = xh_data.get("data", {})
        record = data.get("record", {})

        # 提取tokens - 新格式直接是字符串数组
        tokens_array = record.get("tokens", [])
        if tokens_array:
            tokens.extend(tokens_array)

        # 提取addresses - 新格式直接是字符串数组
        addresses_array = record.get("addresses", [])
        if addresses_array:
            addresses.extend(addresses_array)

    except Exception as e:
        logger.error(f"提取Token和地址时出错: {str(e)}")

    return tokens, addresses, success
