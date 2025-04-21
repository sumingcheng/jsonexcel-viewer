import pandas as pd
import json
import html
import os
import uuid
import tempfile
import logging
import re
from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename

# 设置日志 - 输出到控制台
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("token_analysis")

# 预编译正则表达式，避免重复编译
ETH_ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")
BTC_ADDRESS_PATTERN = re.compile(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}")

app = Flask(__name__)
# 使用固定的密钥，避免每次重启应用时会话失效
app.secret_key = "a_secure_random_secret_key_for_sessions"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>分析工具</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        html, body { height: 100%; margin: 0; overflow-x: hidden; }
        body { padding: 10px 0; }
        .container-fluid { width: 98%; padding: 0 10px; }
        .table-responsive { margin-top: 10px; width: 100%; height: calc(100vh - 150px); overflow-y: auto; position: relative; }
        .table td, .table th { text-align: center; vertical-align: middle; }
        .id-column { width: 60px; }
        .txt-column { text-align: left; word-wrap: break-word; white-space: normal; min-width: 300px; max-width: 400px; }
        .token-column, .address-column { min-width: 150px; max-width: 200px; }
        .detail-column { min-width: 180px; }
        .address-data { font-weight: bold; color: #198754; background-color: #e8f8f0; padding: 2px 5px; border-radius: 3px; display: block; margin: 3px 0; word-wrap: break-word; word-break: break-all; white-space: normal; }
        .token-data { font-weight: bold; color: #0d6efd; background-color: #e7f1ff; padding: 2px 5px; border-radius: 3px; display: block; margin: 3px 0; word-wrap: break-word; word-break: break-all; white-space: normal; }
        .detail-data { display: block; margin: 3px 0; }
        .table { border-collapse: collapse; }
        .table td, .table th { border: 1px solid #dee2e6; }
        .view-toggle { margin-bottom: 10px; }
        .hidden { display: none; }
        
        /* 固定表头样式 */
        .sticky-header {
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: #f8f9fa;
            box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.1);
        }
        
        .table thead th {
            position: sticky;
            top: 0;
            background-color: #f8f9fa;
            z-index: 10;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-12">
                <h1 class="display-10 mb-3">分析工具</h1>
                
                <div class="card mb-3">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0">上传数据文件</h5>
                    </div>
                    <div class="card-body">
                        <form method="post" enctype="multipart/form-data" class="row g-3">
                            <div class="col-md-9">
                                <input type="file" name="file" accept=".xlsx" class="form-control">
                                <div class="form-text">支持Excel文件格式(.xlsx)</div>
                            </div>
                            <div class="col-md-3">
                                <button type="submit" class="btn btn-primary w-100">分析数据</button>
                            </div>
                        </form>
                    </div>
                </div>
                
                {% if error %}
                <div class="alert alert-danger">
                    <strong>错误！</strong> {{ error }}
                </div>
                {% endif %}
                
                {% if stats %}
                <div class="alert alert-info mb-2">
                    <strong>数据统计：</strong>
                    <ul>
                        <li>总记录数: <strong>{{ stats.total_records }}</strong></li>
                        <li>包含Token的记录数: <strong>{{ stats.records_with_tokens }}</strong></li>
                        <li>包含地址的记录数: <strong>{{ stats.records_with_addresses }}</strong></li>
                    </ul>
                </div>
                {% endif %}
                
                {% if token_data_valid or token_data_all %}
                <div class="alert alert-success mb-2">
                    <strong>成功！</strong> 数据已成功加载并分析，共发现 <strong>{{ token_count }}</strong> 条Token或地址信息。
                </div>
                
                <div class="view-toggle btn-group" role="group">
                    <input type="radio" class="btn-check" name="view-option" id="view-valid" autocomplete="off" checked>
                    <label class="btn btn-outline-primary" for="view-valid">显示有效记录</label>
                    
                    <input type="radio" class="btn-check" name="view-option" id="view-all" autocomplete="off">
                    <label class="btn btn-outline-primary" for="view-all">显示全部记录</label>
                </div>
                
                <div class="table-responsive" id="valid-records-table">
                    {{ token_data_valid|safe }}
                </div>
                
                <div class="table-responsive hidden" id="all-records-table">
                    {{ token_data_all|safe }}
                </div>
                
                <script>
                    document.getElementById('view-valid').addEventListener('change', function() {
                        document.getElementById('valid-records-table').classList.remove('hidden');
                        document.getElementById('all-records-table').classList.add('hidden');
                    });
                    
                    document.getElementById('view-all').addEventListener('change', function() {
                        document.getElementById('valid-records-table').classList.add('hidden');
                        document.getElementById('all-records-table').classList.remove('hidden');
                    });
                </script>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
"""

TEMP_FOLDER = tempfile.gettempdir()
os.makedirs(TEMP_FOLDER, exist_ok=True)


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

        # 只从JSON数据中提取信息
        data = xh_data.get("data", {})
        record = data.get("record", {})

        # 提取tokens
        for token_info in record.get("tokens", []):
            token = token_info.get("token")
            if token:
                tokens.append(token)

        # 提取addresses
        for addr_info in record.get("addresses", []):
            address = addr_info.get("address")
            if address:
                addresses.append(address)

    except Exception as e:
        logger.error(f"提取Token和地址时出错: {str(e)}")

    return tokens, addresses, success


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files or request.files["file"].filename == "":
            return render_template_string(HTML_TEMPLATE, error="没有选择文件")

        file = request.files["file"]
        filename = secure_filename(file.filename)

        if not filename.lower().endswith(".xlsx"):
            logger.warning(f"上传了不支持的文件类型: {filename}")
            return render_template_string(
                HTML_TEMPLATE, error="请上传.xlsx格式的Excel文件"
            )

        temp_file = os.path.join(TEMP_FOLDER, f"upload_{uuid.uuid4().hex}.xlsx")
        logger.info(f"开始处理上传文件: {filename}, 临时保存为: {temp_file}")

        try:
            # 保存上传的文件
            file.save(temp_file)

            # 读取Excel文件
            df = pd.read_excel(temp_file, engine="openpyxl")
            df.columns = [col.strip().lower() for col in df.columns]

            total_records = len(df)
            logger.info(f"读取到 {total_records} 条记录")

            required_columns = ["ts", "tid", "txt"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"数据缺少必要的列: {', '.join(missing_columns)}")
                return render_template_string(
                    HTML_TEMPLATE,
                    error=f"数据缺少必要的列：{', '.join(missing_columns)}",
                )

            # 初始化统计信息
            successful_records = 0
            failed_records = 0
            records_with_tokens = 0
            records_with_addresses = 0

            tokens_and_addresses = []
            success_flags = []

            for _, row in df.iterrows():
                try:
                    tokens, addresses, success = extract_tokens_and_addresses(row)
                    tokens_and_addresses.append((tokens, addresses))
                    success_flags.append(success)

                    if not success:
                        failed_records += 1
                    else:
                        successful_records += 1
                        if tokens:
                            records_with_tokens += 1
                        if addresses:
                            records_with_addresses += 1

                except Exception as e:
                    logger.error(
                        f"处理记录时出错, TID: {row.get('tid', 'unknown')}, 错误: {str(e)}"
                    )
                    tokens_and_addresses.append(([], []))
                    success_flags.append(False)  # 修改为False，因为这是处理失败的情况
                    failed_records += 1

            # 生成统计数据
            stats = {
                "total_records": total_records,
                "successful_records": successful_records,
                "failed_records": failed_records,
                "records_with_tokens": records_with_tokens,
                "records_with_addresses": records_with_addresses,
            }

            logger.info(
                f"统计信息: 总记录数={stats['total_records']}, Token记录数={stats['records_with_tokens']}, 地址记录数={stats['records_with_addresses']}, 失败请求数={stats['failed_records']}"
            )

            token_df = pd.DataFrame(
                {
                    "时间": df["ts"],
                    "推文内容": df["txt"],
                    "提取的Token": [item[0] for item in tokens_and_addresses],
                    "提取的地址": [item[1] for item in tokens_and_addresses],
                    "TID": df["tid"],
                    "成功标记": success_flags,
                }
            )

            # 修改筛选条件，包含成功标记为False的记录
            valid_token_df = token_df[
                (token_df["提取的Token"].apply(len) > 0)
                | (token_df["提取的地址"].apply(len) > 0)
                | (~token_df["成功标记"])  # 添加失败记录
            ]

            # 获取全部记录，用于"显示全部记录"选项
            all_token_df = token_df.copy()

            if len(valid_token_df) == 0:
                logger.warning("没有找到有效的Token、地址数据或失败记录")
                return render_template_string(
                    HTML_TEMPLATE,
                    error="没有找到有效的Token、地址数据或失败记录",
                    stats=stats,
                )

            # 生成有效记录的HTML表格
            valid_token_data_html = generate_table_html(valid_token_df)

            # 生成全部记录的HTML表格
            all_token_data_html = generate_table_html(all_token_df)

            logger.info(
                f"分析完成, 找到 {len(valid_token_df)} 条有效Token、地址信息或失败记录，总共 {len(all_token_df)} 条记录"
            )

            # 在HTML模板中显示失败记录数
            HTML_TEMPLATE_WITH_FAILED = HTML_TEMPLATE.replace(
                "<li>包含地址的记录数: <strong>{{ stats.records_with_addresses }}</strong></li>",
                "<li>包含地址的记录数: <strong>{{ stats.records_with_addresses }}</strong></li>\n        <li>失败请求记录数: <strong>{{ stats.failed_records }}</strong></li>",
            )

            return render_template_string(
                HTML_TEMPLATE_WITH_FAILED,
                token_data_valid=valid_token_data_html,
                token_data_all=all_token_data_html,
                token_count=len(valid_token_df),
                stats=stats,
            )

        except Exception as e:
            logger.error(f"处理数据时发生错误: {str(e)}")
            return render_template_string(
                HTML_TEMPLATE, error=f"处理数据时出错: {str(e)}"
            )
        finally:
            # 确保临时文件被删除
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.info(f"已删除临时文件: {temp_file}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {temp_file}, 错误: {str(e)}")

    return render_template_string(HTML_TEMPLATE)


# 添加生成表格的辅助函数
def generate_table_html(df):
    """生成HTML表格"""
    token_data_html = (
        '<table class="table table-striped table-hover" border="0">'
        '<thead class="sticky-header"><tr>'
    )
    for col, col_class in {
        "序号": "id-column",
        "推文": "txt-column",
        "token": "token-column",
        "address": "address-column",
        "其他": "detail-column",
    }.items():
        token_data_html += f'<th class="{col_class}">{col}</th>'
    token_data_html += "</tr></thead><tbody>"

    # 生成表格行
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        # 根据成功标记设置行样式
        is_success = row["成功标记"]
        row_style = "" if is_success else ' style="background-color: #fff3f3;"'

        token_data_html += f"<tr{row_style}>"
        token_data_html += f'<td class="id-column">{idx}</td>'
        token_data_html += (
            f'<td class="txt-column">{html.escape(str(row["推文内容"]))}</td>'
        )

        # 处理Token
        tokens = row["提取的Token"]
        token_html = ""
        if tokens:
            for token in tokens:
                token_html += (
                    f'<span class="token-data">{html.escape(str(token))}</span>'
                )
        token_data_html += f'<td class="token-column">{token_html}</td>'

        # 处理地址
        addresses = row["提取的地址"]
        address_html = ""
        if addresses:
            for addr in addresses:
                address_html += (
                    f'<span class="address-data">{html.escape(str(addr))}</span>'
                )
        token_data_html += f'<td class="address-column">{address_html}</td>'

        # 处理详细信息
        detail_html = (
            f'<span class="detail-data">TID: {html.escape(str(row["TID"]))}</span>'
        )
        detail_html += (
            f'<span class="detail-data">时间: {html.escape(str(row["时间"]))}</span>'
        )
        if not is_success:
            detail_html += f'<span class="detail-data badge bg-danger">失败请求</span>'
        token_data_html += f'<td class="detail-column">{detail_html}</td>'

        token_data_html += "</tr>"

    token_data_html += "</tbody></table>"
    return token_data_html


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=23333)
