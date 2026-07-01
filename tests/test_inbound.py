"""入库管理模块测试 — 核心业务：入库后库存是否正确增加、批次是否正确创建/更新"""
import pytest
from datetime import date, datetime
from models import Consumable, StockBatch, InboundRecord
from tests.conftest import create_consumable, create_inbound


class TestInboundCreate:
    """入库记录创建"""

    def test_create_inbound_success(self, client, app):
        """入库成功：返回201，库存正确增加，批次正确创建"""
        c = create_consumable(client)
        cid = c['id']

        resp = client.post('/api/stock/inbound', json={
            'consumable_id': cid,
            'quantity': 100,
            'batch_number': 'LOT001',
            'production_date': '2025-01-01',
            'expiry_date': '2026-12-31',
            'operator': '张三',
            'storage_location': 'A区1号架',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['quantity'] == 100
        assert data['batch_number'] == 'LOT001'
        assert data['document_number'].startswith('RK')
        assert data['operator'] == '张三'

        # 验证库存批次已创建
        with app.app_context():
            batch = StockBatch.query.filter_by(consumable_id=cid).first()
            assert batch is not None
            assert batch.quantity == 100
            assert batch.batch_number == 'LOT001'

    def test_create_inbound_increases_stock(self, client, app):
        """多次入库后库存总量正确"""
        c = create_consumable(client)
        cid = c['id']

        # 第一次入库 50
        create_inbound(client, cid, quantity=50, batch_number='LOT001')
        # 第二次入库 30
        create_inbound(client, cid, quantity=30, batch_number='LOT002')

        with app.app_context():
            consumable = Consumable.query.get(cid)
            assert consumable.total_stock == 80

    def test_create_inbound_creates_separate_batches(self, client, app):
        """不同批号入库创建独立批次"""
        c = create_consumable(client)
        cid = c['id']

        create_inbound(client, cid, quantity=100, batch_number='LOT-A')
        create_inbound(client, cid, quantity=50, batch_number='LOT-B')

        with app.app_context():
            batches = StockBatch.query.filter_by(consumable_id=cid).all()
            assert len(batches) == 2
            batch_a = next(b for b in batches if b.batch_number == 'LOT-A')
            batch_b = next(b for b in batches if b.batch_number == 'LOT-B')
            assert batch_a.quantity == 100
            assert batch_b.quantity == 50

    def test_create_inbound_auto_document_number(self, client, app):
        """入库单号自动生成，格式 RK+日期+序号"""
        c = create_consumable(client)
        cid = c['id']

        r1 = create_inbound(client, cid, quantity=10)
        r2 = create_inbound(client, cid, quantity=20)

        assert r1['document_number'].startswith('RK')
        assert r2['document_number'].startswith('RK')
        # 两个单号不应相同
        assert r1['document_number'] != r2['document_number']

    def test_create_inbound_missing_required_fields(self, client, app):
        """缺少必填字段返回400"""
        resp = client.post('/api/stock/inbound', json={})
        assert resp.status_code == 400

        resp = client.post('/api/stock/inbound', json={'quantity': 10})
        assert resp.status_code == 400

    def test_create_inbound_nonexistent_consumable(self, client, app):
        """入库不存在的耗材返回404"""
        resp = client.post('/api/stock/inbound', json={
            'consumable_id': 99999,
            'quantity': 10,
        })
        assert resp.status_code == 404

    def test_create_inbound_batch_expiry_date(self, client, app):
        """入库时正确记录生产日期和失效日期"""
        c = create_consumable(client)
        cid = c['id']

        resp = client.post('/api/stock/inbound', json={
            'consumable_id': cid,
            'quantity': 50,
            'batch_number': 'LOT-E',
            'production_date': '2025-06-01',
            'expiry_date': '2027-06-01',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['production_date'] == '2025-06-01'
        assert data['expiry_date'] == '2027-06-01'

        with app.app_context():
            batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-E').first()
            assert batch is not None
            assert batch.production_date == date(2025, 6, 1)
            assert batch.expiry_date == date(2027, 6, 1)


class TestInboundDelete:
    """删除入库记录"""

    def test_delete_inbound_reduces_stock(self, client, app):
        """删除入库记录后库存正确扣减"""
        c = create_consumable(client)
        cid = c['id']

        r = create_inbound(client, cid, quantity=100, batch_number='LOT001')
        record_id = r['id']

        # 删除入库记录
        resp = client.delete(f'/api/stock/inbound/{record_id}')
        assert resp.status_code == 200

        # 验证库存已扣减
        with app.app_context():
            consumable = Consumable.query.get(cid)
            assert consumable.total_stock == 0

    def test_delete_inbound_reduces_batch(self, client, app):
        """删除入库记录后批次库存正确扣减"""
        c = create_consumable(client)
        cid = c['id']

        r = create_inbound(client, cid, quantity=100, batch_number='LOT001')
        record_id = r['id']

        # 删除入库记录
        client.delete(f'/api/stock/inbound/{record_id}')

        with app.app_context():
            batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT001').first()
            # 批次数量扣减到0后被删除
            assert batch is None or batch.quantity == 0

    def test_delete_inbound_partial_batch(self, client, app):
        """同批号多次入库，删除其中一条只扣减对应数量"""
        c = create_consumable(client)
        cid = c['id']

        # 两次入库使用相同批号 — 注意：当前实现每次入库创建独立批次
        r1 = create_inbound(client, cid, quantity=100, batch_number='LOT001')
        create_inbound(client, cid, quantity=50, batch_number='LOT001')

        # 删除第一条入库记录
        client.delete(f'/api/stock/inbound/{r1["id"]}')

        with app.app_context():
            # 应该还有一个批次（第二次入库创建的）
            batches = StockBatch.query.filter_by(consumable_id=cid).all()
            remaining = sum(b.quantity for b in batches)
            assert remaining == 50


class TestInboundList:
    """入库记录查询"""

    def test_list_inbound_with_keyword(self, client, app):
        """按关键词搜索入库记录"""
        c = create_consumable(client, code='HC001', name='口罩')
        create_inbound(client, c['id'], quantity=100, operator='张三')

        resp = client.get('/api/stock/inbound?keyword=张三')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1

    def test_list_inbound_with_date_range(self, client, app):
        """按日期范围筛选入库记录"""
        c = create_consumable(client)
        create_inbound(client, c['id'], quantity=100)

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/inbound?start_date={today}&end_date={today}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1


class TestInboundPrint:
    """入库单打印数据"""

    def test_get_inbound_print_data(self, client, app):
        """获取入库单打印数据"""
        c = create_consumable(client, code='HC001', name='口罩', brand='测试品牌')
        r = create_inbound(client, c['id'], quantity=100, operator='张三')

        resp = client.get(f'/api/stock/inbound/{r["id"]}/print')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['document_number'].startswith('RK')
        assert 'consumable_name' in data
        assert data['consumable_brand'] == '测试品牌'