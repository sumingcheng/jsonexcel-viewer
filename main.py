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

TEMP_FOLDER = tempfile.gettempdir()
os.makedirs(TEMP_FOLDER, exist_ok=True)


def parse_json_data(json_str):
    """Parse JSON string and return empty dict on failure"""
    if pd.isna(json_str) or not isinstance(json_str, str) or json_str.strip() == "":
        return {}
    try:
        return json.loads(json_str)
    except:
        return {}


def extract_tokens_and_addresses(row):
    """Extract token info from xh_model field"""
    tokens = []
    addresses = []

    if "xh_model" in row and not pd.isna(row["xh_model"]):
        xh_data = parse_json_data(row["xh_model"])

        if (
            "data" in xh_data
            and "record" in xh_data.get("data", {})
            and "tokens" in xh_data.get("data", {}).get("record", {})
        ):
            for token_info in xh_data["data"]["record"]["tokens"]:
                if "token" in token_info:
                    tokens.append(token_info["token"])

    return tokens, addresses


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files or request.files["file"].filename == "":
            return render_template_string(HTML_TEMPLATE, error="没有选择文件")

        file = request.files["file"]
        filename = secure_filename(file.filename)

        if not filename.lower().endswith(".xlsx"):
            return render_template_string(
                HTML_TEMPLATE, error="请上传.xlsx格式的Excel文件"
            )

        temp_file = os.path.join(TEMP_FOLDER, f"upload_{uuid.uuid4().hex}.xlsx")

        try:
            file.save(temp_file)
            df = pd.read_excel(temp_file, engine="openpyxl")
            df.columns = [col.strip().lower() for col in df.columns]

            required_columns = ["ts", "tid", "txt"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return render_template_string(
                    HTML_TEMPLATE,
                    error=f"数据缺少必要的列：{', '.join(missing_columns)}",
                )

            tokens_and_addresses = []
            for _, row in df.iterrows():
                tokens, addresses = extract_tokens_and_addresses(row)
                tokens_and_addresses.append((tokens, addresses))

            token_df = pd.DataFrame(
                {
                    "时间": df["ts"],
                    "推文内容": df["txt"],
                    "提取的Token": [item[0] for item in tokens_and_addresses],
                    "提取的地址": [item[1] for item in tokens_and_addresses],
                    "TID": df["tid"],
                }
            )

            valid_token_df = token_df[
                (token_df["提取的Token"].apply(len) > 0)
                | (token_df["提取的地址"].apply(len) > 0)
            ]

            if len(valid_token_df) == 0:
                return render_template_string(
                    HTML_TEMPLATE, error="没有找到有效的Token或地址数据"
                )

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

            for idx, (_, row) in enumerate(valid_token_df.iterrows(), 1):
                token_data_html += "<tr>\n"
                token_data_html += f'<td class="id-column">{idx}</td>\n'
                token_data_html += (
                    f'<td class="txt-column">{html.escape(str(row["推文内容"]))}</td>\n'
                )

                tokens = row["提取的Token"]
                token_html = ""
                if tokens:
                    token_html = "".join(
                        f'<span class="token-data">{html.escape(str(token))}</span>\n'
                        for token in tokens
                    )
                token_data_html += f'<td class="token-column">{token_html}</td>\n'

                addresses = row["提取的地址"]
                address_html = ""
                if addresses:
                    address_html = "".join(
                        f'<span class="address-data">{html.escape(str(addr))}</span>\n'
                        for addr in addresses
                    )
                token_data_html += f'<td class="address-column">{address_html}</td>\n'

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
            if os.path.exists(temp_file):
                os.remove(temp_file)

    return render_template_string(HTML_TEMPLATE)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=23333)
