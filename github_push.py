"""GitHub推送模块"""
import json
import base64
from datetime import datetime
from github import Github, GithubException


class GitHubPusher:
    def __init__(self, token: str, repo_name: str, branch: str = 'main'):
        self.github = Github(token)
        self.repo_name = repo_name
        self.branch = branch
        self.repo = None

    def connect(self):
        """连接到GitHub仓库"""
        try:
            self.repo = self.github.get_repo(self.repo_name)
            return True
        except GithubException as e:
            print(f"连接仓库失败: {e}")
            return False

    def push_usage_data(self, data: dict, data_file: str = 'data/usage_history.json'):
        """推送使用量数据"""
        if not self.repo:
            if not self.connect():
                return False

        try:
            existing_data = self._get_existing_data(data_file)
            existing_data.append(data)

            if len(existing_data) > 500:
                existing_data = existing_data[-500:]

            content = json.dumps(existing_data, indent=2, ensure_ascii=False)
            self._update_file(data_file, content, f"更新数据 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")

            return True

        except Exception as e:
            print(f"推送数据失败: {e}")
            return False

    def push_index_page(self, data_file: str = 'data/usage_history.json'):
        """推送展示页面"""
        if not self.repo:
            if not self.connect():
                return False

        html_content = self._generate_index_html(data_file)

        try:
            self._update_file('index.html', html_content, "更新展示页面")
            return True
        except Exception as e:
            print(f"更新展示页面失败: {e}")
            return False

    def _get_existing_data(self, file_path: str) -> list:
        """获取现有数据"""
        try:
            content_file = self.repo.get_contents(file_path, ref=self.branch)
            content = base64.b64decode(content_file.content).decode('utf-8')
            return json.loads(content)
        except:
            return []

    def _update_file(self, file_path: str, content: str, message: str):
        """更新或创建文件"""
        try:
            existing_file = self.repo.get_contents(file_path, ref=self.branch)
            self.repo.update_file(
                path=file_path,
                message=message,
                content=content,
                sha=existing_file.sha,
                branch=self.branch
            )
        except GithubException as e:
            if e.status == 404:
                self.repo.create_file(
                    path=file_path,
                    message=message,
                    content=content,
                    branch=self.branch
                )
            else:
                raise

    def _generate_index_html(self, data_file: str) -> str:
        """生成展示页面"""
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GLM 使用量监控</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{
            text-align: center;
            margin-bottom: 30px;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
        .stat-card {{
            flex: 1;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
        }}
        .stat-value {{ font-size: 3em; font-weight: bold; }}
        .stat-value.warning {{ color: #ffc107; }}
        .stat-value.danger {{ color: #ff6b6b; }}
        .stat-value.ok {{ color: #00d2ff; }}
        .stat-label {{ color: #aaa; margin-top: 10px; }}
        .chart-container {{
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
        }}
        .update-time {{ text-align: center; color: #666; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GLM Coding Plan 使用量</h1>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="hourly">-</div>
                <div class="stat-label">5小时额度使用</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="weekly">-</div>
                <div class="stat-label">每周额度使用</div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="chart"></canvas>
        </div>
        <div class="update-time" id="updateTime">加载中...</div>
    </div>
    <script>
        async function load() {{
            const res = await fetch('{data_file}');
            const data = await res.json();
            if (!data.length) return;

            const latest = data[data.length - 1];
            const h = latest.hourly_quota_percent ?? 0;
            const w = latest.weekly_quota_percent ?? 0;

            const hourlyEl = document.getElementById('hourly');
            const weeklyEl = document.getElementById('weekly');

            hourlyEl.textContent = h.toFixed(1) + '%';
            weeklyEl.textContent = w.toFixed(1) + '%';

            hourlyEl.className = 'stat-value ' + (h > 80 ? 'danger' : h > 50 ? 'warning' : 'ok');
            weeklyEl.className = 'stat-value ' + (w > 80 ? 'danger' : w > 50 ? 'warning' : 'ok');

            document.getElementById('updateTime').textContent =
                '更新于: ' + new Date(latest.timestamp).toLocaleString('zh-CN');

            new Chart(document.getElementById('chart'), {{
                type: 'line',
                data: {{
                    labels: data.slice(-50).map(d => new Date(d.timestamp)),
                    datasets: [
                        {{
                            label: '5小时额度%',
                            data: data.slice(-50).map(d => d.hourly_quota_percent),
                            borderColor: '#00d2ff',
                            tension: 0.3
                        }},
                        {{
                            label: '每周额度%',
                            data: data.slice(-50).map(d => d.weekly_quota_percent),
                            borderColor: '#ff6b6b',
                            tension: 0.3
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        x: {{ type: 'time', ticks: {{ color: '#aaa' }} }},
                        y: {{ min: 0, max: 100, ticks: {{ color: '#aaa' }} }}
                    }}
                }}
            }});
        }}
        load();
    </script>
</body>
</html>'''
