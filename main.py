import gradio as gr
import pandas as pd
import json
import os
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter


def format_json(json_str):
    """格式化JSON字符串以便更好地展示"""
    try:
        # 尝试解析JSON字符串
        parsed_json = json.loads(json_str)
        # 返回格式化的JSON
        return json.dumps(parsed_json, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"JSON解析错误: {str(e)}\n原始内容: {json_str}"


def extract_json_fields(json_str):
    """从JSON字符串中提取字段并创建一个扁平的字典"""
    try:
        parsed = json.loads(json_str)
        flattened = {}

        def flatten_dict(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, (dict, list)):
                        flatten_dict(v, new_key)
                    else:
                        flattened[new_key] = v
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_key = f"{prefix}[{i}]"
                    if isinstance(item, (dict, list)):
                        flatten_dict(item, new_key)
                    else:
                        flattened[new_key] = item

        flatten_dict(parsed)
        return flattened
    except Exception as e:
        return {"error": str(e)}


def get_json_structure(json_str):
    """获取JSON的结构（键和数据类型）"""
    try:
        parsed = json.loads(json_str)
        structure = {}

        def analyze_structure(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, (dict, list)):
                        analyze_structure(v, new_key)
                    else:
                        structure[new_key] = type(v).__name__
            elif isinstance(obj, list) and len(obj) > 0:
                # 只分析列表的第一个元素作为示例
                sample = obj[0]
                new_key = f"{prefix}[0]"
                if isinstance(sample, (dict, list)):
                    analyze_structure(sample, new_key)
                else:
                    structure[prefix] = f"list of {type(sample).__name__}"

        analyze_structure(parsed)
        return structure
    except Exception as e:
        return {"error": str(e)}


def process_excel(file):
    """处理上传的Excel文件并返回处理后的数据"""
    try:
        # 读取Excel文件
        df = pd.read_excel(file.name)

        # 获取列名并找到最后一列
        columns = df.columns.tolist()
        last_column = columns[-1]

        # 创建结果数据框
        result_df = pd.DataFrame()
        result_df['行号'] = range(1, len(df) + 1)

        # 添加所有原始列
        for col in columns:
            result_df[col] = df[col]

        # 添加格式化后的JSON列
        result_df['格式化JSON'] = df[last_column].apply(lambda x: format_json(str(x)) if pd.notna(x) else "")

        # 预览数据
        preview_text = f"文件包含 {len(df)} 行数据，共 {len(columns)} 列\n"
        preview_text += f"最后一列名称: {last_column}\n"

        # 返回结果
        return result_df, preview_text, last_column
    except Exception as e:
        return None, f"处理文件时出错: {str(e)}", None


def display_row_json(df, row_index, json_column_name):
    """显示选定行的JSON数据"""
    if df is None or df.empty or row_index < 0 or row_index >= len(df):
        return "没有选择有效的行", {}, {}

    # 获取该行的格式化JSON
    formatted_json = df.iloc[row_index]['格式化JSON']

    # 获取原始JSON字符串
    json_str = str(df.iloc[row_index][json_column_name])

    # 提取JSON字段和结构
    fields = extract_json_fields(json_str)
    structure = get_json_structure(json_str)

    return formatted_json, fields, structure


def analyze_json_dataset(df, json_column_name):
    """分析整个数据集中的JSON数据"""
    if df is None or df.empty:
        return "没有有效的数据集", None

    try:
        # 收集所有出现的字段
        all_fields = set()
        field_types = {}
        field_counts = Counter()
        valid_json_count = 0
        invalid_json_count = 0

        # 分析每行的JSON
        for i, row in df.iterrows():
            json_str = str(row[json_column_name])
            try:
                parsed = json.loads(json_str)
                valid_json_count += 1

                # 提取字段
                fields = extract_json_fields(json_str)
                for field, value in fields.items():
                    all_fields.add(field)
                    field_counts[field] += 1

                    # 记录字段类型
                    field_type = type(value).__name__
                    if field not in field_types:
                        field_types[field] = set()
                    field_types[field].add(field_type)

            except:
                invalid_json_count += 1

        # 生成分析报告
        report = f"JSON数据分析报告:\n"
        report += f"- 有效JSON条目: {valid_json_count}\n"
        report += f"- 无效JSON条目: {invalid_json_count}\n"
        report += f"- 共发现字段数: {len(all_fields)}\n\n"

        # 创建字段统计数据框
        field_stats = []
        for field in sorted(all_fields):
            field_stats.append({
                "字段名": field,
                "出现次数": field_counts[field],
                "出现比例": f"{field_counts[field] / valid_json_count * 100:.2f}%" if valid_json_count > 0 else "0%",
                "数据类型": ", ".join(field_types.get(field, ["未知"]))
            })

        field_stats_df = pd.DataFrame(field_stats)

        return report, field_stats_df
    except Exception as e:
        return f"分析过程中出错: {str(e)}", None


def generate_field_distribution_chart(df, json_column_name, selected_fields):
    """生成所选字段的分布图表"""
    if df is None or df.empty or not selected_fields:
        return None

    try:
        # 提取所有行的字段值
        field_values = {field: [] for field in selected_fields}

        for i, row in df.iterrows():
            json_str = str(row[json_column_name])
            try:
                fields = extract_json_fields(json_str)
                for field in selected_fields:
                    if field in fields:
                        value = fields[field]
                        # 只记录数值和字符串类型
                        if isinstance(value, (int, float)):
                            field_values[field].append(value)
                        elif isinstance(value, str):
                            field_values[field].append(value)
            except:
                pass

        # 创建临时文件名
        chart_path = "temp_chart.png"

        # 设置图表
        fig, axes = plt.subplots(len(selected_fields), 1, figsize=(10, 4 * len(selected_fields)))
        if len(selected_fields) == 1:
            axes = [axes]  # 确保axes始终是列表

        for i, field in enumerate(selected_fields):
            values = field_values[field]
            if not values:
                axes[i].text(0.5, 0.5, f"没有 {field} 的数据", ha='center', va='center')
                continue

            if all(isinstance(x, (int, float)) for x in values):
                # 数值型数据用直方图
                axes[i].hist(values, bins=20, alpha=0.7)
                axes[i].set_title(f"{field} 分布")
                axes[i].set_xlabel("值")
                axes[i].set_ylabel("频次")
            elif all(isinstance(x, str) for x in values):
                # 字符串数据用条形图，显示前10个最常见的值
                value_counts = Counter(values).most_common(10)
                labels, counts = zip(*value_counts) if value_counts else ([], [])
                axes[i].barh(range(len(labels)), counts, alpha=0.7)
                axes[i].set_yticks(range(len(labels)))
                axes[i].set_yticklabels([str(l)[:20] for l in labels])  # 限制标签长度
                axes[i].set_title(f"{field} 前10个最常见值")
                axes[i].set_xlabel("频次")
            else:
                axes[i].text(0.5, 0.5, f"{field} 包含混合数据类型", ha='center', va='center')

        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()

        return chart_path
    except Exception as e:
        print(f"生成图表出错: {str(e)}")
        return None


# 创建全局变量
processed_df = None
json_column = None


def upload_and_process(file):
    """上传并处理文件"""
    global processed_df, json_column
    if file is None:
        return (None, "请上传Excel文件",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False))

    df, preview, last_column = process_excel(file)
    processed_df = df
    json_column = last_column

    # 计算最大行号用于滑块
    max_row = len(df) - 1 if df is not None and not df.empty else 0

    # 如果处理成功，显示数据框和滑块
    dataframe_visible = df is not None and not df.empty

    # 进行数据集分析
    analysis_report, field_stats = analyze_json_dataset(df, last_column) if dataframe_visible else ("", None)

    # 返回预览信息和可见性设置
    return (preview, "",
            gr.update(value=df if dataframe_visible else None, visible=dataframe_visible),
            gr.update(value=analysis_report, visible=dataframe_visible),
            gr.update(value=field_stats if dataframe_visible else None, visible=dataframe_visible),
            gr.update(minimum=0, maximum=max_row, step=1, value=0, visible=dataframe_visible),
            gr.update(visible=dataframe_visible))


def update_json_display(row_index):
    """更新JSON显示"""
    global processed_df, json_column
    if processed_df is None or json_column is None:
        return "", None, None

    formatted_json, fields, structure = display_row_json(processed_df, row_index, json_column)

    # 将字段转换为数据框格式
    fields_df = pd.DataFrame(list(fields.items()), columns=['字段', '值']) if fields else None
    structure_df = pd.DataFrame(list(structure.items()), columns=['字段', '数据类型']) if structure else None

    return formatted_json, fields_df, structure_df


def create_chart(selected_fields):
    """创建所选字段的图表"""
    global processed_df, json_column
    if processed_df is None or json_column is None:
        return None

    chart_path = generate_field_distribution_chart(processed_df, json_column, selected_fields)
    return chart_path


def create_interface():
    """创建Gradio界面"""
    with gr.Blocks(title="Excel JSON 可视化工具") as app:
        gr.Markdown("# Excel JSON 可视化工具")
        gr.Markdown("上传Excel文件，查看并可视化最后一列的JSON数据")

        with gr.Row():
            file_input = gr.File(label="上传Excel文件")

        with gr.Row():
            process_btn = gr.Button("处理文件", variant="primary")

        with gr.Row():
            preview_output = gr.Textbox(label="文件预览", lines=3)
            error_output = gr.Textbox(label="错误信息", lines=3)

        with gr.Row():
            row_slider = gr.Slider(minimum=0, maximum=0, step=1, label="选择行号", visible=False)

        # 创建选项卡
        with gr.Tabs() as tabs:
            with gr.TabItem("数据表格"):
                df_output = gr.Dataframe(label="Excel数据", visible=False)

            with gr.TabItem("JSON视图"):
                with gr.Row():
                    json_display = gr.Textbox(label="JSON数据", lines=15, visible=False)

            with gr.TabItem("字段提取"):
                with gr.Row():
                    fields_display = gr.Dataframe(label="提取的字段", visible=False)

            with gr.TabItem("JSON结构"):
                with gr.Row():
                    structure_display = gr.Dataframe(label="JSON结构", visible=False)

            with gr.TabItem("数据集分析"):
                with gr.Row():
                    analysis_report = gr.Textbox(label="分析报告", lines=6, visible=False)

                with gr.Row():
                    field_stats = gr.Dataframe(label="字段统计", visible=False)

                with gr.Row():
                    field_selector = gr.CheckboxGroup(
                        label="选择要可视化的字段",
                        choices=[],
                        visible=False
                    )
                    generate_chart_btn = gr.Button("生成图表", visible=False)

                with gr.Row():
                    chart_output = gr.Image(label="字段分布图表", visible=False)

        # 设置事件处理
        process_btn.click(
            fn=upload_and_process,
            inputs=[file_input],
            outputs=[preview_output, error_output, df_output, analysis_report, field_stats, row_slider, field_selector]
        )

        row_slider.change(
            fn=update_json_display,
            inputs=[row_slider],
            outputs=[json_display, fields_display, structure_display]
        )

        def update_field_choices():
            global processed_df, json_column
            if processed_df is None or json_column is None:
                return []

            # 分析结果以获取字段名称
            _, field_stats_df = analyze_json_dataset(processed_df, json_column)
            if field_stats_df is not None:
                field_choices = field_stats_df["字段名"].tolist()
                # 只返回前10个字段作为选择
                return gr.update(choices=field_choices[:10], visible=True), gr.update(visible=True), gr.update(
                    visible=True)
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

        # 当处理完文件后，更新字段选择器
        process_btn.click(
            fn=update_field_choices,
            inputs=[],
            outputs=[field_selector, generate_chart_btn, chart_output]
        )

        generate_chart_btn.click(
            fn=create_chart,
            inputs=[field_selector],
            outputs=[chart_output]
        )

    return app


# 启动应用
if __name__ == "__main__":
    app = create_interface()
    app.launch()