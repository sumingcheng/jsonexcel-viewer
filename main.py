import pandas as pd
import json
import html
import os
import uuid
import tempfile
from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
        .table-responsive { margin-top: 10px; width: 100%; height: calc(100vh - 180px); overflow-y: auto; }
        .table td, .table th { text-align: center; vertical-align: middle; }
        .id-column { width: 60px; }
        .txt-column { text-align: left; word-wrap: break-word; white-space: normal; min-width: 300px; max-width: 400px; }
        .token-column, .address-column { min-width: 150px; max-width: 200px; }
        .detail-column { min-width: 180px; }
        .address-data { font-weight: bold; color: #198754; background-color: #e8f8f0; padding: 2px 5px; border-radius: 3px; display: block; margin: 3px 0; }
        .token-data { font-weight: bold; color: #0d6efd; background-color: #e7f1ff; padding: 2px 5px; border-radius: 3px; display: block; margin: 3px 0; }
        .detail-data { display: block; margin: 3px 0; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-12">
                <h1 class="display-5 mb-3">分析工具</h1>
                
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
                
                {% if token_data %}
                <div class="alert alert-success mb-2">
                    <strong>成功！</strong> 数据已成功加载并分析，共发现 <strong>{{ token_count }}</strong> 条Token信息。
                </div>
                
                <div class="table-responsive">
                    {{ token_data|safe }}
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
"""

# 创建临时文件目录
TEMP_FOLDER = tempfile.gettempdir()
os.makedirs(TEMP_FOLDER, exist_ok=True)


def parse_json_data(json_str):
    """尝试解析 JSON 字符串，如果失败则返回空字典"""
    if pd.isna(json_str) or not isinstance(json_str, str) or json_str.strip() == "":
        return {}
    try:
        return json.loads(json_str)
    except:
        return {}


def extract_tokens_and_addresses(json_data):
    """从JSON数据中提取verification_tokens中的symbol和token_address"""
    tokens = []
    addresses = []

    if not json_data:
        return tokens, addresses

    # 只有当status为success且verified_tokens_found为true时才提取
    if (
        json_data.get("status") == "success"
        and json_data.get("verified_tokens_found") == True
    ):
        # 提取verification_tokens中的数据
        if "verification_tokens" in json_data and isinstance(
            json_data["verification_tokens"], list
        ):
            for token in json_data["verification_tokens"]:
                if isinstance(token, dict):
                    if "symbol" in token:
                        tokens.append(token["symbol"])
                    if "token_address" in token:
                        addresses.append(token["token_address"])

    return tokens, addresses


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # 检查是否有文件上传
        if "file" not in request.files or request.files["file"].filename == "":
            return render_template_string(HTML_TEMPLATE, error="没有选择文件")

        file = request.files["file"]
        filename = secure_filename(file.filename)

        # 检查文件扩展名
        if not filename.lower().endswith(".xlsx"):
            return render_template_string(
                HTML_TEMPLATE, error="请上传.xlsx格式的Excel文件"
            )

        # 生成唯一的文件名
        temp_file = os.path.join(TEMP_FOLDER, f"upload_{uuid.uuid4().hex}.xlsx")

        try:
            # 保存上传的文件
            file.save(temp_file)

            # 读取Excel文件
            df = pd.read_excel(temp_file, engine="openpyxl")

            # 处理列名
            df.columns = [col.strip().lower() for col in df.columns]

            # 检查必要的列是否存在
            required_columns = ["ts", "tid", "txt", "ret"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return render_template_string(
                    HTML_TEMPLATE,
                    error=f"数据缺少必要的列：{', '.join(missing_columns)}",
                )

            # 解析 ret 列中的 JSON 数据并提取tokens和addresses
            df["ret_json"] = df["ret"].apply(parse_json_data)
            tokens_and_addresses = df["ret_json"].apply(extract_tokens_and_addresses)

            # 创建Token展示DataFrame
            token_df = pd.DataFrame(
                {
                    "时间": df["ts"],
                    "推文内容": df["txt"],
                    "提取的Token": tokens_and_addresses.apply(
                        lambda x: x[0] if x[0] else []
                    ),
                    "提取的地址": tokens_and_addresses.apply(
                        lambda x: x[1] if x[1] else []
                    ),
                    "TID": df["tid"],
                }
            )

            # 仅保留有效数据（存在token或address的行）
            valid_token_df = token_df[
                (token_df["提取的Token"].apply(len) > 0)
                | (token_df["提取的地址"].apply(len) > 0)
            ]

            if len(valid_token_df) == 0:
                return render_template_string(
                    HTML_TEMPLATE, error="没有找到有效的Token或地址数据"
                )

            # 生成HTML表格
            token_data_html = '<table class="table table-striped table-hover" border="0">\n<thead>\n<tr>\n'
            for col, col_class in {
                "序号": "id-column",
                "推文内容": "txt-column",
                "提取的Token": "token-column",
                "提取的地址": "address-column",
                "详细": "detail-column",
            }.items():
                token_data_html += f'<th class="{col_class}">{col}</th>\n'
            token_data_html += "</tr>\n</thead>\n<tbody>\n"

            # 添加数据行
            for idx, (_, row) in enumerate(valid_token_df.iterrows(), 1):
                token_data_html += "<tr>\n"

                # 序号列
                token_data_html += f'<td class="id-column">{idx}</td>\n'

                # 推文内容列
                token_data_html += (
                    f'<td class="txt-column">{html.escape(str(row["推文内容"]))}</td>\n'
                )

                # 提取的Token列
                tokens = row["提取的Token"]
                token_html = ""
                if tokens:
                    token_html = "".join(
                        f'<span class="token-data">{html.escape(str(token))}</span>\n'
                        for token in tokens
                    )
                token_data_html += f'<td class="token-column">{token_html}</td>\n'

                # 提取的地址列
                addresses = row["提取的地址"]
                address_html = ""
                if addresses:
                    address_html = "".join(
                        f'<span class="address-data">{html.escape(str(addr))}</span>\n'
                        for addr in addresses
                    )
                token_data_html += f'<td class="address-column">{address_html}</td>\n'

                # 详细列
                detail_html = f'<span class="detail-data">TID: {html.escape(str(row["TID"]))}</span>\n'
                detail_html += f'<span class="detail-data">时间: {html.escape(str(row["时间"]))}</span>\n'
                token_data_html += f'<td class="detail-column">{detail_html}</td>\n'

                token_data_html += "</tr>\n"

            token_data_html += "</tbody>\n</table>"

            return render_template_string(
                HTML_TEMPLATE,
                token_data=token_data_html,
                token_count=len(valid_token_df),
            )

        except Exception as e:
            return render_template_string(
                HTML_TEMPLATE, error=f"处理数据时出错: {str(e)}"
            )
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)

    # GET请求时显示上传表单
    return render_template_string(HTML_TEMPLATE)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=23333)
