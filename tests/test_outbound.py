"""出库管理模块测试 — FIFO 扣减逻辑、库存不足校验、出库后库存正确减少"""
import pytest
from datetime import date, timedelta
from models import Consumable, StockBatch, OutboundRecord
from tests.conftest import create_consumable, create_inbound, create_outbound


class TestOutboundCreate:
    """出库记录创建"""

    def test_create_outbound_success(self, client, app):
        """出库成功：返回201，库存正确减少"""
        c = create_consumable(client)
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid,
            'quantity': 30,
            'recipient': '李四',
            'department': '门诊检验科',
            'operator': '张三',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['quantity'] == 30
        assert data['document_number'].startswith('CK')
        assert data['recipient'] == '李四'
        assert data['department'] == '门诊检验科'

        # 验证库存
        with app.app_context():
            consumable = Consumable.query.get(cid)
            assert consumable.total_stock == 70

    def test_create_outbound_insufficient_stock(self, client, app):
        """库存不足时出库返回400"""
        c = create_consumable(client)
        cid = c['id']
        create_inbound(client, cid, quantity=10, batch_number='LOT001')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid,
            'quantity': 20,
        })
        assert resp.status_code == 400
        assert '库存不足' in resp.get_json()['error']

    def test_create_outbound_zero_stock(self, client, app):
        """无库存时出库返回400"""
        c = create_consumable(client)
        cid = c['id']

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid,
            'quantity': 1,
        })
        assert resp.status_code == 400

    def test_create_outbound_auto_document_number(self, client, app):
        """出库单号自动生成，格式 CK+日期+序号"""
        c = create_consumable(client)
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')

        r1 = create_outbound(client, cid, quantity=10)
        r2 = create_outbound(client, cid, quantity=10)

        assert r1['document_number'].startswith('CK')
        assert r2['document_number'].startswith('CK')
        assert r1['document_number'] != r2['document_number']

    def test_create_outbound_nonexistent_consumable(self, client, app):
        """出库不存在的耗材返回404"""
        resp = client.post('/api/stock/outbound', json={
            'consumable_id': 99999,
            'quantity': 1,
        })
        assert resp.status_code == 404


class TestOutboundFIFO:
    """FIFO 先进先出扣减逻辑"""

    def test_fifo_deducts_earliest_expiry_first(self, client, app):
        """FIFO：优先扣减最早过期的批次"""
        c = create_consumable(client)
        cid = c['id']

        # 入库两个批次，第一个批次先过期
        create_inbound(client, cid, quantity=50, batch_number='LOT-EARLY',
                       expiry_date='2025-12-31')
        create_inbound(client, cid, quantity=50, batch_number='LOT-LATE',
                       expiry_date='2027-12-31')

        # 出库30，应从 LOT-EARLY 扣减
        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid,
            'quantity': 30,
        })
        assert resp.status_code == 201

        with app.app_context():
            early_batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-EARLY').first()
            late_batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-LATE').first()
            assert early_batch.quantity == 20  # 50 - 30
            assert late_batch.quantity == 50   # 未扣减

    def test_fifo_cross_batch_deduction(self, client, app):
        """FIFO：第一个批次数量不足时，跨批次扣减"""
        c = create_consumable(client)
        cid = c['id']

        # 入库两个批次
        create_inbound(client, cid, quantity=30, batch_number='LOT-A',
                       expiry_date='2025-12-31')
        create_inbound(client, cid, quantity=50, batch_number='LOT-B',
                       expiry_date='2027-12-31')

        # 出库50，LOT-A 30 + LOT-B 20
        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid,
            'quantity': 50,
        })
        assert resp.status_code == 201

        with app.app_context():
            # LOT-A 应被扣完（已删除或为0）
            early_batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-A').first()
            assert early_batch is None or early_batch.quantity == 0

            late_batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-B').first()
            assert late_batch.quantity == 30  # 50 - 20

    def test_fifo_specified_batch(self, client, app):
        """指定批号出库：从指定批次扣减"""
        c = create_consumable(client)
        cid = c['id']

        create_inbound(client, cid, quantity=100, batch_number='LOT-SPEC',
                       expiry_date='2027-12-31')
        create_inbound(client, cid, quantity=100, batch_number='LOT-OTHER',
                       expiry_date='2026-12-31')

        # 指定从 LOT-SPEC 出库
        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid,
            'quantity': 40,
            'batch_number': 'LOT-SPEC',
        })
        assert resp.status_code == 201

        with app.app_context():
            spec_batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-SPEC').first()
            other_batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-OTHER').first()
            assert spec_batch.quantity == 60   # 100 - 40
            assert other_batch.quantity == 100  # 未扣减

    def test_fifo_total_stock_after_multiple_outbound(self, client, app):
        """多次出库后总库存正确"""
        c = create_consumable(client)
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')

        create_outbound(client, cid, quantity=30)
        create_outbound(client, cid, quantity=20)
        create_outbound(client, cid, quantity=10)

        with app.app_context():
            consumable = Consumable.query.get(cid)
            assert consumable.total_stock == 40  # 100 - 30 - 20 - 10


class TestOutboundDelete:
    """删除出库记录"""

    def test_delete_outbound_restores_stock(self, client, app):
        """删除出库记录后库存恢复"""
        c = create_consumable(client)
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')

        r = create_outbound(client, cid, quantity=30, batch_number='LOT001')
        record_id = r['id']

        # 删除出库记录
        resp = client.delete(f'/api/stock/outbound/{record_id}')
        assert resp.status_code == 200

        # 验证库存恢复
        with app.app_context():
            consumable = Consumable.query.get(cid)
            assert consumable.total_stock == 100


class TestOutboundList:
    """出库记录查询"""

    def test_list_outbound_with_keyword(self, client, app):
        """按关键词搜索出库记录"""
        c = create_consumable(client, code='HC001', name='口罩')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        create_outbound(client, c['id'], quantity=10, recipient='王五', department='住院部')

        resp = client.get('/api/stock/outbound?keyword=王五')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1

    def test_list_outbound_with_date_range(self, client, app):
        """按日期范围筛选出库记录"""
        c = create_consumable(client)
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')
        create_outbound(client, c['id'], quantity=10)

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/outbound?start_date={today}&end_date={today}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1

    def test_list_outbound_by_department(self, client, app):
        """按科室筛选出库记录"""
        c = create_consumable(client)
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')
        create_outbound(client, c['id'], quantity=10, department='住院部')

        resp = client.get('/api/stock/outbound?keyword=住院部')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1


class TestOutboundBatchMode:
    """批量出库"""

    def test_batch_outbound(self, client, app):
        """批量出库多个耗材"""
        c1 = create_consumable(client, code='HC001', name='耗材A')
        c2 = create_consumable(client, code='HC002', name='耗材B')
        create_inbound(client, c1['id'], quantity=100, batch_number='LOT001')
        create_inbound(client, c2['id'], quantity=200, batch_number='LOT002')

        resp = client.post('/api/stock/outbound', json={
            'items': [
                {'consumable_id': c1['id'], 'quantity': 10},
                {'consumable_id': c2['id'], 'quantity': 20},
            ],
            'recipient': '王五',
            'department': '住院部',
            'operator': '张三',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['count'] == 2
        assert data['document_number'].startswith('CK')

        # 验证库存
        with app.app_context():
            assert Consumable.query.get(c1['id']).total_stock == 90
            assert Consumable.query.get(c2['id']).total_stock == 180

    def test_batch_outbound_insufficient_stock_rollback(self, client, app):
        """批量出库中某项库存不足时整体失败"""
        c1 = create_consumable(client, code='HC001', name='耗材A')
        c2 = create_consumable(client, code='HC002', name='耗材B')
        create_inbound(client, c1['id'], quantity=100, batch_number='LOT001')
        create_inbound(client, c2['id'], quantity=5, batch_number='LOT002')

        resp = client.post('/api/stock/outbound', json={
            'items': [
                {'consumable_id': c1['id'], 'quantity': 10},
                {'consumable_id': c2['id'], 'quantity': 20},  # 库存不足
            ],
            'recipient': '王五',
            'department': '住院部',
        })
        # 应该返回400
        assert resp.status_code == 400


class TestOutboundPrint:
    """出库单打印数据"""

    def test_get_outbound_print_data(self, client, app):
        """获取出库单打印数据"""
        c = create_consumable(client, code='HC001', name='口罩', brand='品牌A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        r = create_outbound(client, c['id'], quantity=10, recipient='王五', department='住院部')

        resp = client.get(f'/api/stock/outbound/{r["id"]}/print')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['document_number'].startswith('CK')
        assert 'consumable_name' in data
        assert data['department'] == '住院部'