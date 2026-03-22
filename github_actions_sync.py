"""GitHub Actions 专用同步脚本"""
import os
import json
import asyncio
import re
from datetime import datetime, timezone, timedelta
from scraper import GLMScraper

# 中国时区 UTC+8
CN_TIMEZONE = timezone(timedelta(hours=8))

DATA_FILE = 'data/usage_history.json'
README_FILE = 'README.md'


def load_history():
    """加载历史数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_history(data):
    """保存历史数据"""
    os.makedirs('data', exist_ok=True)
    history = load_history()
    history.append(data)
    if len(history) > 500:
        history = history[-500:]
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, indent=2, ensure_ascii=False, fp=f)
    print(f"数据已保存到 {DATA_FILE}")


def make_progress_bar(percent, width=25):
    """生成进度条"""
    filled = int(percent / 100 * width)
    bar = '▓' * filled + '░' * (width - filled)
    if percent > 80:
        status = '🔴 **警告**'
    elif percent > 50:
        status = '🟡 **注意**'
    else:
        status = '🟢 **正常**'
    return f'`{bar}` {status}'


def update_readme(data):
    """更新 README.md"""
    if not os.path.exists(README_FILE):
        print("README.md 不存在")
        return

    with open(README_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    hourly = data.get('hourly_quota_percent') or 0
    weekly = data.get('weekly_quota_percent') or 0
    update_time = datetime.now(tz=CN_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
    hourly_reset = data.get('hourly_reset_time') or '未知'
    weekly_reset = data.get('weekly_reset_time') or '未知'

    # 替换占位符
    content = re.sub(r'<!-- UPDATE_TIME -->', update_time, content)
    content = re.sub(r'<!-- HOURLY -->', f'{hourly:.0f}', content)
    content = re.sub(r'<!-- WEEKLY -->', f'{weekly:.0f}', content)
    content = re.sub(r'<!-- HOURLY_BAR -->', make_progress_bar(hourly), content)
    content = re.sub(r'<!-- WEEKLY_BAR -->', make_progress_bar(weekly), content)
    content = re.sub(r'<!-- HOURLY_RESET -->', hourly_reset, content)
    content = re.sub(r'<!-- WEEKLY_RESET -->', weekly_reset, content)

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"README.md 已更新")


async def main():
    cookie = os.environ.get('ZHIPU_COOKIE')
    if not cookie:
        print("错误: 未设置 ZHIPU_COOKIE 环境变量")
        return

    print(f"开始获取数据... {datetime.now().isoformat()}")

    scraper = GLMScraper(cookie=cookie)
    data = await scraper.get_usage_data()

    print(f"获取结果: {json.dumps(data, ensure_ascii=False, indent=2)}")

    if 'error' not in data:
        save_history(data)
        update_readme(data)
        print("同步完成!")
    else:
        print(f"获取失败: {data.get('error')}")


if __name__ == '__main__':
    asyncio.run(main())
