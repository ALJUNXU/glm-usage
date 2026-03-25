"""智谱AI使用量爬虫模块"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright

# 中国时区 UTC+8
CN_TIMEZONE = timezone(timedelta(hours=8))


class GLMScraper:
    TARGET_URL = "https://bigmodel.cn/usercenter/glm-coding/usage"

    def __init__(self, cookie: str = None):
        self.cookie = cookie
        self.cookie_valid = None  # Cookie 有效性状态

    async def get_usage_data(self) -> dict:
        """获取使用量数据"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            if self.cookie:
                cookies = self._parse_cookie_string(self.cookie)
                await context.add_cookies(cookies)

            page = await context.new_page()

            try:
                api_data = None
                login_required = False

                async def handle_response(response):
                    nonlocal api_data, login_required
                    try:
                        data = await response.json()
                        # 检测是否需要登录
                        if data.get('code') == 401 or '登录' in str(data.get('msg', '')):
                            login_required = True
                        # 获取限额数据
                        if isinstance(data.get('data'), dict) and 'limits' in data.get('data', {}):
                            api_data = data['data']
                    except:
                        pass

                page.on('response', handle_response)
                await page.goto(self.TARGET_URL, wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(5000)

                # 检测 Cookie 有效性
                if login_required:
                    self.cookie_valid = False
                    return {
                        'error': 'Cookie 已失效，请更新 ZHIPU_COOKIE',
                        'cookie_expired': True,
                        'timestamp': datetime.now().isoformat()
                    }

                if api_data:
                    self.cookie_valid = True
                    return self._extract_limits(api_data)

                # 检测页面是否跳转到登录页
                current_url = page.url
                if 'login' in current_url.lower():
                    self.cookie_valid = False
                    return {
                        'error': 'Cookie 已失效，请更新 ZHIPU_COOKIE',
                        'cookie_expired': True,
                        'timestamp': datetime.now().isoformat()
                    }

                return {'error': '未获取到数据', 'timestamp': datetime.now().isoformat()}

            finally:
                await browser.close()

    def _extract_limits(self, data: dict) -> dict:
        """从 limits 数组提取数据"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'hourly_quota_percent': None,
            'weekly_quota_percent': None,
            'hourly_reset_time': None,
            'weekly_reset_time': None,
            'level': data.get('level')
        }

        for limit in data.get('limits', []):
            if limit.get('type') != 'TOKENS_LIMIT':
                continue

            unit = limit.get('unit')
            percentage = limit.get('percentage')
            reset_time = limit.get('nextResetTime')

            # unit=3 是5小时额度, unit=6 是每周额度
            if unit == 3:
                result['hourly_quota_percent'] = percentage
                result['hourly_reset_time'] = self._format_reset_time(reset_time)
            elif unit == 6:
                result['weekly_quota_percent'] = percentage
                result['weekly_reset_time'] = self._format_reset_time(reset_time)

        return result

    def _format_reset_time(self, timestamp_ms: int) -> str:
        """格式化重置时间（中国时区）"""
        if not timestamp_ms:
            return None
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=CN_TIMEZONE)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _parse_cookie_string(self, cookie_string: str) -> list:
        """解析cookie字符串"""
        cookies = []
        for item in cookie_string.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': '.bigmodel.cn',
                    'path': '/'
                })
        return cookies


if __name__ == '__main__':
    async def test():
        cookie = input("请输入Cookie: ")
        scraper = GLMScraper(cookie=cookie)
        data = await scraper.get_usage_data()
        print(json.dumps(data, indent=2, ensure_ascii=False))

    asyncio.run(test())
