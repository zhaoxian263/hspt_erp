"""库存查询模块测试 — 期间库存计算逻辑、预警状态判定逻辑"""
import pytest
from datetime import date, timedelta
from models import Consumable, StockBatch
from tests.conftest import create_consumable, create_inbound, create_outbound


class TestInventoryList:
    """库存总览"""

    def test_inventory_shows_stock_status(self, client, app):
        """库存总览显示库存状态"""
        c = create_consumable(client, code='HC001', name='口罩', stock_warning_value=20)
        create_inbound(client, c['id'], quantity=50, batch_number='LOT001')

        resp = client.get('/api/stock/inventory')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1
        item = next(i for i in data['items'] if i['id'] == c['id'])
        assert item['total_stock'] == 50

    def test_inventory_filter_normal(self, client, app):
        """按库存状态筛选 - 正常"""
        c = create_consumable(client, code='HC-NORMAL', name='正常耗材', stock_warning_value=5)
        create_inbound(client, c['id'], quantity=50, batch_number='LOT001')

        resp = client.get('/api/stock/inventory?status=normal')
        assert resp.status_code == 200
        data = resp.get_json()
        for item in data['items']:
            assert item['stock_status'] == '库存正常'

    def test_inventory_filter_low_or_warning(self, client, app):
        """按库存状态筛选 - 预警/不足"""
        c = create_consumable(client, code='HC-LOW', name='低库存耗材', stock_warning_value=100)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        resp = client.get('/api/stock/inventory?status=low_or_warning')
        assert resp.status_code == 200
        data = resp.get_json()
        # 库存10 <= 预警值100，应在结果中
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids

    def test_inventory_shows_batches(self, client, app):
        """库存总览包含批次明细"""
        c = create_consumable(client, code='HC-BATCH', name='批次耗材')
        create_inbound(client, c['id'], quantity=50, batch_number='LOT-A',
                       expiry_date='2025-12-31')
        create_inbound(client, c['id'], quantity=30, batch_number='LOT-B',
                       expiry_date='2027-12-31')

        resp = client.get('/api/stock/inventory')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == c['id'])
        assert len(item['stock_batches']) == 2


class TestStockStatus:
    """库存预警状态判定"""

    def test_stock_status_normal(self, client, app):
        """库存状态：正常（库存 > 预警值 × 1.5）"""
        c = create_consumable(client, code='HC-SN', name='正常', stock_warning_value=10)
        create_inbound(client, c['id'], quantity=20, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.stock_status == '库存正常'

    def test_stock_status_warning(self, client, app):
        """库存状态：预警（库存 ≤ 预警值 × 1.5 且 > 预警值）"""
        c = create_consumable(client, code='HC-SW', name='预警', stock_warning_value=10)
        create_inbound(client, c['id'], quantity=12, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            # 12 <= 10*1.5=15 且 12 > 10
            assert consumable.stock_status == '库存预警'

    def test_stock_status_low(self, client, app):
        """库存状态：不足（库存 ≤ 预警值 且 > 0）"""
        c = create_consumable(client, code='HC-SL', name='不足', stock_warning_value=10)
        create_inbound(client, c['id'], quantity=5, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            # 5 <= 10
            assert consumable.stock_status == '库存不足'

    def test_stock_status_zero(self, client, app):
        """库存状态：不足（库存为0）"""
        c = create_consumable(client, code='HC-SZ', name='零库存', stock_warning_value=10)

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.total_stock == 0
            assert consumable.stock_status == '库存不足'


class TestExpiryStatus:
    """效期预警状态判定"""

    def test_expiry_status_normal(self, client, app):
        """效期状态：正常（失效日期远于预警天数）"""
        c = create_consumable(client, code='HC-EN', name='效期正常', expiry_warning_days=30)
        future_date = (date.today() + timedelta(days=365)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=future_date)

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.expiry_status == '效期正常'

    def test_expiry_status_near_expiry(self, client, app):
        """效期状态：近效期（失效日期 ≤ 今天 + 预警天数）"""
        c = create_consumable(client, code='HC-EW', name='近效期', expiry_warning_days=90)
        near_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=near_date)

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.expiry_status == '近效期'

    def test_expiry_status_expired(self, client, app):
        """效期状态：已过期（失效日期 < 今天）"""
        c = create_consumable(client, code='HC-EE', name='已过期', expiry_warning_days=30)
        past_date = (date.today() - timedelta(days=10)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=past_date)

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.expiry_status == '已过期'

    def test_expiry_filter_expired(self, client, app):
        """按效期状态筛选 - 已过期"""
        c = create_consumable(client, code='HC-EF', name='过滤过期', expiry_warning_days=30)
        past_date = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=past_date)

        resp = client.get('/api/stock/inventory?status=expired')
        data = resp.get_json()
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids

    def test_expiry_filter_near_expiry(self, client, app):
        """按效期状态筛选 - 近效期"""
        c = create_consumable(client, code='HC-EFW', name='过滤近效期', expiry_warning_days=90)
        near_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=near_date)

        resp = client.get('/api/stock/inventory?status=expiry_warning')
        data = resp.get_json()
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids


class TestBatchDetail:
    """批次明细"""

    def test_list_batches(self, client, app):
        """查看某耗材的批次明细"""
        c = create_consumable(client, code='HC-BD', name='批次耗材')
        create_inbound(client, c['id'], quantity=50, batch_number='LOT-A',
                       expiry_date='2025-12-31')
        create_inbound(client, c['id'], quantity=30, batch_number='LOT-B',
                       expiry_date='2027-12-31')

        resp = client.get(f'/api/stock/batches?consumable_id={c["id"]}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] == 2
        # 批次应按失效日期排序（早的在前）
        assert data['items'][0]['batch_number'] == 'LOT-A'

    def test_list_batches_only_positive_quantity(self, client, app):
        """批次明细只显示库存大于0的批次"""
        c = create_consumable(client, code='HC-BP', name='批次正数')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-ZERO')
        # 出库完
        create_outbound(client, c['id'], quantity=10, batch_number='LOT-ZERO')

        resp = client.get(f'/api/stock/batches?consumable_id={c["id"]}')
        data = resp.get_json()
        # 零库存批次不应显示
        assert data['total'] == 0


class TestPeriodInventory:
    """期间库存查询"""

    def test_period_inventory_calculation(self, client, app):
        """期间库存计算：期初 + 入库 - 出库 = 期末"""
        c = create_consumable(client, code='HC-PI', name='期间库存', initial_stock=100)
        cid = c['id']
        create_inbound(client, cid, quantity=50, batch_number='LOT001')
        create_outbound(client, cid, quantity=30, batch_number='LOT001')

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        assert resp.status_code == 200
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)
        assert item['initial_stock'] == 100
        assert item['period_inbound'] == 50
        assert item['period_outbound'] == 30
        assert item['ending_stock'] == 120  # 100 + 50 - 30

    def test_period_inventory_requires_dates(self, client, app):
        """期间库存查询需要日期参数"""
        resp = client.get('/api/stock/period-inventory')
        assert resp.status_code == 400

    def test_period_inventory_with_keyword(self, client, app):
        """期间库存查询支持关键词搜索"""
        c = create_consumable(client, code='HC-PK', name='关键词测试')
        create_inbound(client, c['id'], quantity=50, batch_number='LOT001')

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}&keyword=关键词')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1


class TestDashboard:
    """仪表盘"""

    def test_dashboard_basic_stats(self, client, app):
        """仪表盘返回基本统计数据"""
        c = create_consumable(client, code='HC-DB', name='仪表盘耗材', stock_warning_value=5)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        resp = client.get('/api/stock/dashboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_consumables' in data
        assert 'total_stock' in data
        assert 'warning_count' in data
        assert 'expired_count' in data
        assert 'trend' in data
        assert 'days' in data['trend']
        assert 'inbound' in data['trend']
        assert 'outbound' in data['trend']

    def test_dashboard_warning_items(self, client, app):
        """仪表盘包含库存预警列表"""
        c = create_consumable(client, code='HC-DW', name='预警耗材', stock_warning_value=100)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        resp = client.get('/api/stock/dashboard')
        data = resp.get_json()
        assert data['warning_count'] >= 1

    def test_dashboard_dept_stats(self, client, app):
        """仪表盘包含科室出库统计"""
        c = create_consumable(client, code='HC-DD', name='科室统计耗材')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')
        create_outbound(client, c['id'], quantity=10, department='住院部')

        resp = client.get('/api/stock/dashboard')
        data = resp.get_json()
        dept_data = [d for d in data['dept_stats'] if d['department'] == '住院部']
        assert len(dept_data) >= 1
        assert dept_data[0]['total'] >= 10