from boot.config import ROOT_CONFIG
from utils.config import Config, LazySetting

__all__ = ['CONFIG', 'shihannet']


class BirthboardConfig(Config):
    # 页脚"联系我们"邮箱：点击通过 mailto 打开系统邮件客户端
    contact_email = LazySetting('contact_email', default='', type=str)


CONFIG = BirthboardConfig(ROOT_CONFIG, 'birthboard')


class ShihannetConfig(Config):
    """Playwright 登录外部投放屏（shihannet）的账号配置。"""
    username = LazySetting('username', default='', type=str)
    password = LazySetting('password', default='', type=str)
    url = LazySetting('url', default='', type=str)


shihannet = ShihannetConfig(ROOT_CONFIG.get('shihannet', {}))
