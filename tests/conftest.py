"""测试基础设施：内存数据库 + Flask 测试客户端"""
import pytest
from app import create_app
from models import db as _db, Consumable, StockBatch, InboundRecord, OutboundRecord, \
    Department, Category, Staff, InventoryCheck, InventoryCheckItem


@pytest.fixture(scope='function')
def app():
    """每个测试函数使用独立的内存数据库"""
    app = create_app()
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    with app.app_context():
        _db.create_all()
        # 初始化默认科室和类别
        _init_default_departments()
        _init_default_categories()

    yield app

    with app.app_context():
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """数据库实例（带 app context）"""
    with app.app_context():
        yield _db


def _init_default_departments():
    """初始化默认科室"""
    if Department.query.count() == 0:
        defaults = ['门诊检验科', '住院部', '手术室', '急诊科', 'ICU', '儿科',
                    '妇产科', '骨科', '内科', '外科', '药房', '行政后勤']
        for idx, name in enumerate(defaults):
            _db.session.add(Department(name=name, sort_order=idx))
        _db.session.commit()


def _init_default_categories():
    """初始化默认类别"""
    if Category.query.count() == 0:
        defaults = ['一次性耗材', '试剂耗材', '敷料耗材', '器械耗材', '药品耗材', '其他耗材']
        for idx, name in enumerate(defaults):
            _db.session.add(Category(name=name, sort_order=idx))
        _db.session.commit()


# ==================== 通用辅助函数 ====================

def create_consumable(client, code='HC001', name='测试耗材', **kwargs):
    """辅助函数：创建耗材并返回响应 JSON"""
    data = {'code': code, 'name': name}
    data.update(kwargs)
    resp = client.post('/api/consumables', json=data)
    return resp.get_json()


def create_inbound(client, consumable_id, quantity=100, **kwargs):
    """辅助函数：创建入库记录并返回响应 JSON"""
    data = {'consumable_id': consumable_id, 'quantity': quantity}
    data.update(kwargs)
    resp = client.post('/api/stock/inbound', json=data)
    return resp.get_json()


def create_outbound(client, consumable_id=None, quantity=10, **kwargs):
    """辅助函数：创建出库记录并返回响应 JSON"""
    data = {'consumable_id': consumable_id, 'quantity': quantity}
    data.update(kwargs)
    resp = client.post('/api/stock/outbound', json=data)
    return resp.get_json()


def create_category(client, name='测试类别', **kwargs):
    """辅助函数：创建类别并返回响应 JSON"""
    data = {'name': name}
    data.update(kwargs)
    resp = client.post('/api/categories', json=data)
    return resp.get_json()


def create_staff(client, name='张三', **kwargs):
    """辅助函数：创建人员并返回响应 JSON"""
    data = {'name': name}
    data.update(kwargs)
    resp = client.post('/api/staff', json=data)
    return resp.get_json()


def create_department(client, name='测试科室', **kwargs):
    """辅助函数：创建科室并返回响应 JSON"""
    data = {'name': name}
    data.update(kwargs)
    resp = client.post('/api/departments', json=data)
    return resp.get_json()