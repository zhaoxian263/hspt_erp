import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'database')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'erp.db')

SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

SECRET_KEY = os.environ.get('ERP_SECRET_KEY', os.urandom(24).hex())

# 上传文件大小限制64MB
MAX_CONTENT_LENGTH = 64 * 1024 * 1024

# 分页默认值
PAGE_SIZE = 20