#!/usr/bin/env python3
"""GLM Coding Plan 使用量监控 - Web界面版"""
import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from scraper import GLMScraper
from github_push import GitHubPusher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 配置文件路径
CONFIG_FILE = 'data/config.json'
DATA_FILE = 'data/usage_history.json'
LOG_FILE = 'logs/app.log'

# 确保目录存在
Path('data').mkdir(exist_ok=True)
Path('logs').mkdir(exist_ok=True)


def load_config():
    """加载配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'zhipu_cookie': '',
        'github_token': '',
        'github_repo': '',
        'auto_refresh': False,
        'refresh_interval': 30
    }


def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_usage_data():
    """加载使用量历史数据"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []


def save_usage_data(data):
    """保存使用量数据"""
    history = load_usage_data()
    history.append(data)
    # 保留最近500条
    if len(history) > 500:
        history = history[-500:]
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def read_logs(lines=100):
    """读取日志"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except:
            pass
    return "暂无日志"


async def fetch_usage_async(cookie):
    """异步获取使用量"""
    scraper = GLMScraper(cookie=cookie)
    return await scraper.get_usage_data()


def sync_to_github(config, data):
    """同步数据到GitHub"""
    if not config.get('github_token') or not config.get('github_repo'):
        logger.warning("GitHub配置不完整，跳过同步")
        return False

    try:
        pusher = GitHubPusher(
            token=config['github_token'],
            repo_name=config['github_repo']
        )
        pusher.push_usage_data(data, 'data/usage_history.json')
        pusher.push_index_page('data/usage_history.json')
        logger.info("数据已同步到GitHub")
        return True
    except Exception as e:
        logger.error(f"同步GitHub失败: {e}")
        return False


# ============== 路由 ==============

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    config = load_config()
    # 隐藏敏感信息
    safe_config = {
        'zhipu_cookie': '***已设置***' if config.get('zhipu_cookie') else '',
        'github_token': '***已设置***' if config.get('github_token') else '',
        'github_repo': config.get('github_repo', ''),
        'auto_refresh': config.get('auto_refresh', False),
        'refresh_interval': config.get('refresh_interval', 30)
    }
    return jsonify(safe_config)


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    config = load_config()
    data = request.json

    # 只更新提供的字段
    if 'zhipu_cookie' in data and data['zhipu_cookie'] and not data['zhipu_cookie'].startswith('***'):
        config['zhipu_cookie'] = data['zhipu_cookie']
    if 'github_token' in data and data['github_token'] and not data['github_token'].startswith('***'):
        config['github_token'] = data['github_token']
    if 'github_repo' in data:
        config['github_repo'] = data['github_repo']
    if 'auto_refresh' in data:
        config['auto_refresh'] = data['auto_refresh']
    if 'refresh_interval' in data:
        config['refresh_interval'] = int(data['refresh_interval'])

    save_config(config)
    logger.info("配置已更新")
    return jsonify({'success': True, 'message': '配置已保存'})


@app.route('/api/usage', methods=['GET'])
def get_usage():
    """获取当前使用量数据"""
    config = load_config()

    if not config.get('zhipu_cookie'):
        return jsonify({'error': '请先配置Cookie'}), 400

    try:
        logger.info("开始获取使用量数据...")
        data = asyncio.run(fetch_usage_async(config['zhipu_cookie']))

        # 保存数据
        save_usage_data(data)

        # 同步到GitHub
        if config.get('github_token') and config.get('github_repo'):
            sync_to_github(config, data)

        logger.info(f"获取数据成功: {data}")
        return jsonify(data)

    except Exception as e:
        logger.error(f"获取使用量失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/usage/history', methods=['GET'])
def get_usage_history():
    """获取历史数据"""
    history = load_usage_data()
    # 返回最近50条
    return jsonify(history[-50:])


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取日志"""
    lines = request.args.get('lines', 100, type=int)
    logs = read_logs(lines)
    return jsonify({'logs': logs})


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取系统状态"""
    config = load_config()
    history = load_usage_data()

    status = {
        'configured': bool(config.get('zhipu_cookie')),
        'github_configured': bool(config.get('github_token') and config.get('github_repo')),
        'last_update': history[-1]['timestamp'] if history else None,
        'total_records': len(history),
        'auto_refresh': config.get('auto_refresh', False),
        'refresh_interval': config.get('refresh_interval', 30)
    }
    return jsonify(status)


if __name__ == '__main__':
    print("=" * 50)
    print("GLM Coding Plan 使用量监控")
    print("=" * 50)
    print(f"访问地址: http://localhost:5000")
    print(f"配置文件: {CONFIG_FILE}")
    print(f"数据文件: {DATA_FILE}")
    print(f"日志文件: {LOG_FILE}")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, debug=True)
