import pandas as pd
import html
import os
import uuid
import logging
from flask import request, render_template_string, send_file
from werkzeug.utils import secure_filename
from html_template import HTML_TEMPLATE
from utils import extract_tokens_and_addresses

# 获取logger
logger = logging.getLogger("token_analysis")

# 全局变量存储最新的分析结果
latest_analysis_data = None


def register_routes(app, temp_folder):
    """注册所有路由到Flask应用"""

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

            temp_file = os.path.join(temp_folder, f"upload_{uuid.uuid4().hex}.xlsx")
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
                missing_columns = [
                    col for col in required_columns if col not in df.columns
                ]
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
                        success_flags.append(False)
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

                # 保存分析结果用于导出
                global latest_analysis_data
                latest_analysis_data = all_token_df.copy()

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
                    show_export=True,
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

    @app.route("/export")
    def export_data():
        """导出全部分析结果为Excel文件"""
        global latest_analysis_data

        if latest_analysis_data is None:
            logger.warning("尝试导出但没有分析数据")
            return render_template_string(
                HTML_TEMPLATE, error="没有可导出的数据，请先上传并分析文件"
            )

        try:
            # 创建临时文件
            temp_export_file = os.path.join(
                temp_folder, f"export_{uuid.uuid4().hex}.xlsx"
            )

            # 处理数据格式
            export_df = latest_analysis_data.copy()

            # 将Token和地址列表转换为字符串
            export_df["提取的Token"] = export_df["提取的Token"].apply(
                lambda x: ", ".join(x) if isinstance(x, list) and x else ""
            )
            export_df["提取的地址"] = export_df["提取的地址"].apply(
                lambda x: ", ".join(x) if isinstance(x, list) and x else ""
            )

            # 重命名列为更友好的名称
            export_df = export_df.rename(
                columns={
                    "时间": "推文时间",
                    "推文内容": "推文内容",
                    "提取的Token": "提取的Token",
                    "提取的地址": "提取的地址",
                    "TID": "推文ID",
                    "成功标记": "处理状态",
                }
            )

            # 将处理状态转换为更友好的文本
            export_df["处理状态"] = export_df["处理状态"].apply(
                lambda x: "成功" if x else "失败"
            )

            # 重新排列列的顺序
            column_order = [
                "推文时间",
                "推文ID",
                "推文内容",
                "提取的Token",
                "提取的地址",
                "处理状态",
            ]
            export_df = export_df.reindex(columns=column_order)

            # 导出到Excel
            export_df.to_excel(temp_export_file, index=False, sheet_name="分析结果")

            logger.info(f"导出文件已生成: token_analysis_results.xlsx")

            return send_file(
                temp_export_file,
                as_attachment=True,
                download_name="token_analysis_results.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except Exception as e:
            logger.error(f"导出数据时发生错误: {str(e)}")
            return render_template_string(
                HTML_TEMPLATE, error=f"导出数据时出错: {str(e)}"
            )


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
