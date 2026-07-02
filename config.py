import os
import hashlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'database')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'erp.db')

SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# SECRET_KEY：优先从环境变量读取；否则基于数据库路径生成固定值，避免每次重启变化导致 session 失效
_SECRET_SEED = f'erp-sys-{DATABASE_PATH}'
SECRET_KEY = os.environ.get('ERP_SECRET_KEY', hashlib.sha256(_SECRET_SEED.encode()).hexdigest())

# 上传文件大小限制64MB
MAX_CONTENT_LENGTH = 64 * 1024 * 1024

# 分页默认值
PAGE_SIZE = 20