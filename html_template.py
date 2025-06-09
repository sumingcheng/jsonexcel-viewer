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
