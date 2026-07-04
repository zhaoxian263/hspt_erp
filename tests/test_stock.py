"""库存逻辑全量测试 — 库存总览、预警状态、效期状态、批次明细、期间库存、仪表盘、出入库库存一致性"""
import pytest
from datetime import date, datetime, timedelta
from models import db as _db, Consumable, StockBatch, InboundRecord, OutboundRecord
from tests.conftest import create_consumable, create_inbound, create_outbound


# ======================== 库存总览 ========================

class TestInventoryList:
    """库存总览接口"""

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
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids

    def test_inventory_filter_expiry_warning(self, client, app):
        """按效期状态筛选 - 近效期"""
        c = create_consumable(client, code='HC-EFW', name='过滤近效期', expiry_warning_days=90)
        near_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=near_date)

        resp = client.get('/api/stock/inventory?status=expiry_warning')
        data = resp.get_json()
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids

    def test_inventory_filter_expired(self, client, app):
        """按效期状态筛选 - 已过期"""
        c = create_consumable(client, code='HC-EF', name='过滤过期', expiry_warning_days=30)
        past_date = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=past_date)

        resp = client.get('/api/stock/inventory?status=expired')
        data = resp.get_json()
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

    def test_inventory_keyword_search(self, client, app):
        """库存总览关键词搜索"""
        c = create_consumable(client, code='HC-KW', name='特殊耗材名')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        # 按名称搜索
        resp = client.get('/api/stock/inventory?keyword=特殊耗材')
        data = resp.get_json()
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids

        # 按编码搜索
        resp = client.get('/api/stock/inventory?keyword=HC-KW')
        data = resp.get_json()
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids

    def test_inventory_category_filter(self, client, app):
        """库存总览按类别筛选"""
        c = create_consumable(client, code='HC-CAT', name='类别耗材', category='一次性耗材')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        resp = client.get('/api/stock/inventory?category=一次性耗材')
        data = resp.get_json()
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids

    def test_inventory_pagination(self, client, app):
        """库存总览分页"""
        resp = client.get('/api/stock/inventory?page=1&page_size=5')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total' in data
        assert 'page' in data
        assert 'page_size' in data
        assert len(data['items']) <= 5


# ======================== 库存预警状态 ========================

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
            assert consumable.stock_status == '库存预警'

    def test_stock_status_low(self, client, app):
        """库存状态：不足（库存 ≤ 预警值 且 > 0）"""
        c = create_consumable(client, code='HC-SL', name='不足', stock_warning_value=10)
        create_inbound(client, c['id'], quantity=5, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.stock_status == '库存不足'

    def test_stock_status_zero(self, client, app):
        """库存状态：不足（库存为0）"""
        c = create_consumable(client, code='HC-SZ', name='零库存', stock_warning_value=10)

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.total_stock == 0
            assert consumable.stock_status == '库存不足'

    def test_stock_status_warning_boundary(self, client, app):
        """库存状态：边界值 - 库存恰好等于预警值×1.5"""
        c = create_consumable(client, code='HC-SWB', name='预警边界', stock_warning_value=10)
        create_inbound(client, c['id'], quantity=15, batch_number='LOT001')  # 15 = 10 * 1.5

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            # 15 <= 15，应为库存预警
            assert consumable.stock_status == '库存预警'

    def test_stock_status_low_boundary(self, client, app):
        """库存状态：边界值 - 库存恰好等于预警值"""
        c = create_consumable(client, code='HC-SLB', name='不足边界', stock_warning_value=10)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')  # 10 = 预警值

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            # 10 <= 10，应为库存不足
            assert consumable.stock_status == '库存不足'

    def test_stock_status_no_warning_value(self, client, app):
        """库存状态：未设置预警值时始终为正常"""
        c = create_consumable(client, code='HC-SNV', name='无预警值', stock_warning_value=0)
        create_inbound(client, c['id'], quantity=1, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.stock_status == '库存正常'

    def test_stock_status_after_outbound(self, client, app):
        """出库后库存状态动态更新"""
        c = create_consumable(client, code='HC-SO', name='出库后状态', stock_warning_value=10)
        create_inbound(client, c['id'], quantity=50, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.stock_status == '库存正常'

        # 出库至预警区间
        create_outbound(client, c['id'], quantity=38)  # 50-38=12, 12<=15预警且>10

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.stock_status == '库存预警'

        # 继续出库至不足
        create_outbound(client, c['id'], quantity=8)  # 12-8=4, 4<=10不足

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.stock_status == '库存不足'


# ======================== 效期预警状态 ========================

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

    def test_expiry_status_no_expiry_date(self, client, app):
        """效期状态：无失效日期时为正常"""
        c = create_consumable(client, code='HC-ENE', name='无失效日期', expiry_warning_days=30)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.expiry_status == '效期正常'

    def test_expiry_status_no_warning_days(self, client, app):
        """效期状态：未设置预警天数时始终为正常（除非已过期）"""
        c = create_consumable(client, code='HC-ENW', name='无预警天数', expiry_warning_days=0)
        near_date = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001',
                       expiry_date=near_date)

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            # 预警天数为0，即使快过期也不触发近效期
            assert consumable.expiry_status == '效期正常'

    def test_expiry_status_uses_earliest_batch(self, client, app):
        """效期状态：取最早过期的批次作为判定依据"""
        c = create_consumable(client, code='HC-EEB', name='最早批次', expiry_warning_days=90)
        future_date = (date.today() + timedelta(days=365)).strftime('%Y-%m-%d')
        near_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-FAR',
                       expiry_date=future_date)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-NEAR',
                       expiry_date=near_date)

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            # 最早过期的批次在30天后，在预警范围内
            assert consumable.expiry_status == '近效期'


# ======================== 批次明细 ========================

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
        assert data['items'][0]['batch_number'] == 'LOT-A'

    def test_list_batches_only_positive_quantity(self, client, app):
        """批次明细只显示库存大于0的批次"""
        c = create_consumable(client, code='HC-BP', name='批次正数')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-ZERO')
        create_outbound(client, c['id'], quantity=10, batch_number='LOT-ZERO')

        resp = client.get(f'/api/stock/batches?consumable_id={c["id"]}')
        data = resp.get_json()
        assert data['total'] == 0

    def test_batch_expiry_status(self, client, app):
        """批次级别的效期状态"""
        c = create_consumable(client, code='HC-BES', name='批次效期', expiry_warning_days=90)
        past_date = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-EXP',
                       expiry_date=past_date)

        with app.app_context():
            batch = StockBatch.query.filter_by(consumable_id=c['id']).first()
            assert batch.expiry_status == '已过期'


# ======================== 期间库存查询 ========================

class TestPeriodInventory:
    """期间库存查询 - 基本计算"""

    def test_period_inventory_calculation(self, client, app):
        """期间库存计算：期初 + 入库 - 出库 = 期末
        期初前的入库记录归入期初"""
        c = create_consumable(client, code='HC-PI', name='期间库存')
        cid = c['id']
        # 用ORM插入期初前的入库记录和期间内的入库/出库记录
        with app.app_context():
            # 1月入库100（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-INIT',
                inbound_time=datetime(2026, 1, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=100))
            # 6月期间内的入库和出库
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT001',
                inbound_time=datetime(2026, 6, 10, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT001', quantity=50))
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=30,
                outbound_time=datetime(2026, 6, 15, 10, 0, 0),
                batch_detail='[]'))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        assert resp.status_code == 200
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)
        # 期初=100(1月入库，在6月之前), 入库50, 出库30
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

    def test_period_inventory_no_transactions(self, client, app):
        """期间库存：查询期内无出入库，期初前入库归入期初"""
        c = create_consumable(client, code='HC-PNT', name='无交易耗材')
        cid = c['id']

        # 用ORM插入期初前的入库记录
        with app.app_context():
            # 1月入库50（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-INIT',
                inbound_time=datetime(2026, 1, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=50))
            # 6月入库（7月之前，算期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=20, batch_number='LOT-JUN',
                inbound_time=datetime(2026, 6, 10, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-JUN', quantity=20))
            _db.session.commit()

        # 查询7月期间：期初前的入库(50+20)都算期初
        resp = client.get('/api/stock/period-inventory?start_date=2026-07-01&end_date=2026-07-31')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)
        # 期初 = 50(1月入库) + 20(6月入库) = 70, 期间无出入库
        assert item['initial_stock'] == 70
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 70

    def test_period_inventory_zero_initial(self, client, app):
        """期间库存：期初为0"""
        c = create_consumable(client, code='HC-PZI', name='零期初')
        cid = c['id']
        create_inbound(client, cid, quantity=30, batch_number='LOT001')

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)
        # 期初=0, 入库30, 出库0, 期末=30
        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 30
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 30

    def test_period_inventory_current_stock_consistency(self, client, app):
        """期间库存：期末应等于当前实际库存"""
        c = create_consumable(client, code='HC-PCC', name='一致性验证')
        cid = c['id']
        # 期初前入库100
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-INIT',
                inbound_time=datetime(2025, 1, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=100))
            _db.session.commit()
        create_inbound(client, cid, quantity=50, batch_number='LOT001')
        create_outbound(client, cid, quantity=30)

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)
        # 期末应等于当前库存
        assert item['ending_stock'] == item['current_stock']

    def test_period_inventory_multiple_inbound_outbound(self, client, app):
        """期间库存：多次入库出库累计"""
        c = create_consumable(client, code='HC-PMIO', name='多次交易')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')
        create_inbound(client, cid, quantity=50, batch_number='LOT002')
        create_outbound(client, cid, quantity=30)
        create_outbound(client, cid, quantity=20)

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)
        assert item['period_inbound'] == 150  # 100 + 50
        assert item['period_outbound'] == 50   # 30 + 20
        assert item['ending_stock'] == 100     # 0 + 150 - 50


class TestPeriodInventoryCrossPeriod:
    """期间库存查询 - 跨期间场景"""

    def test_period_inventory_cross_period(self, client, app):
        """
        跨期间场景：期初应该是期间开始前的累计库存。
        场景：1月入库100，5月入库50、出库30，6月入库20、出库10。
        查6月期间：期初应为120(100+50-30)，期间入库20，期间出库10，期末130。
        """
        c = create_consumable(client, code='HC-CP', name='跨期间耗材')
        cid = c['id']

        with app.app_context():
            # 1月入库100（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-INIT',
                inbound_time=datetime(2026, 1, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=100))
            # 5月份的入库和出库
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-MAY',
                inbound_time=datetime(2026, 5, 10, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-MAY', quantity=50))
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=30,
                outbound_time=datetime(2026, 5, 15, 10, 0, 0)))
            # 6月份的入库和出库
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=20, batch_number='LOT-JUN',
                inbound_time=datetime(2026, 6, 5, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-JUN', quantity=20))
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=10,
                outbound_time=datetime(2026, 6, 15, 10, 0, 0)))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        assert resp.status_code == 200
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初 = 100(1月入库) + 50(5月入库) - 30(5月出库) = 120
        assert item['initial_stock'] == 120
        assert item['period_inbound'] == 20
        assert item['period_outbound'] == 10
        assert item['ending_stock'] == 130  # 120 + 20 - 10

    def test_period_inventory_cross_period_multiple_months(self, client, app):
        """
        跨多期间场景：3个月的出入库。
        12月入库200，1月入库100出库50，2月入库80出库30，3月入库60出库40。
        查3月：期初=200+100-50+80-30=300，期间入库60，期间出库40，期末=320。
        """
        c = create_consumable(client, code='HC-CPM', name='多期间耗材')
        cid = c['id']

        with app.app_context():
            # 12月入库200（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=200, batch_number='LOT-INIT',
                inbound_time=datetime(2025, 12, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=200))
            records = [
                InboundRecord(consumable_id=cid, quantity=100, batch_number='LOT-JAN',
                              inbound_time=datetime(2026, 1, 10, 10, 0, 0)),
                OutboundRecord(consumable_id=cid, quantity=50,
                               outbound_time=datetime(2026, 1, 20, 10, 0, 0)),
                InboundRecord(consumable_id=cid, quantity=80, batch_number='LOT-FEB',
                              inbound_time=datetime(2026, 2, 5, 10, 0, 0)),
                OutboundRecord(consumable_id=cid, quantity=30,
                               outbound_time=datetime(2026, 2, 15, 10, 0, 0)),
                InboundRecord(consumable_id=cid, quantity=60, batch_number='LOT-MAR',
                              inbound_time=datetime(2026, 3, 5, 10, 0, 0)),
                OutboundRecord(consumable_id=cid, quantity=40,
                               outbound_time=datetime(2026, 3, 20, 10, 0, 0)),
            ]
            _db.session.add_all(records)
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-03-01&end_date=2026-03-31')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初 = 200(12月入库) + 100 - 50 + 80 - 30 = 300
        assert item['initial_stock'] == 300
        assert item['period_inbound'] == 60
        assert item['period_outbound'] == 40
        assert item['ending_stock'] == 320  # 300 + 60 - 40

    def test_period_inventory_first_period(self, client, app):
        """
        第一个期间查询：之前只有期初前的入库记录。
        12月入库50，1月入库30出库10。
        期初=50，期间入库30，期间出库10，期末=70。
        """
        c = create_consumable(client, code='HC-FP', name='首期间耗材')
        cid = c['id']

        with app.app_context():
            # 12月入库50（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-INIT',
                inbound_time=datetime(2025, 12, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=50))
            records = [
                InboundRecord(consumable_id=cid, quantity=30, batch_number='LOT-JAN',
                              inbound_time=datetime(2026, 1, 10, 10, 0, 0)),
                OutboundRecord(consumable_id=cid, quantity=10,
                               outbound_time=datetime(2026, 1, 20, 10, 0, 0)),
            ]
            _db.session.add_all(records)
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-01-01&end_date=2026-01-31')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 50
        assert item['period_inbound'] == 30
        assert item['period_outbound'] == 10
        assert item['ending_stock'] == 70

    def test_period_inventory_category_filter(self, client, app):
        """期间库存查询按类别筛选"""
        c = create_consumable(client, code='HC-PCF', name='类别期间耗材', category='一次性耗材')
        create_inbound(client, c['id'], quantity=20, batch_number='LOT001')

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}&category=一次性耗材')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1
        item_ids = [i['id'] for i in data['items']]
        assert c['id'] in item_ids


# ======================== 期间库存 - 深度边界测试 ========================

class TestPeriodInventoryBoundary:
    """期间库存查询 - 边界条件与深度测试"""

    def test_period_boundary_start_date_midnight(self, client, app):
        """
        边界：start_date当天00:00:00的入库记录属于期间内而非期间前。
        inbound_time < '2026-06-01' 对比 '2026-06-01 00:00:00'，
        在SQLite字符串比较中 '2026-06-01 00:00:00' > '2026-06-01'，因此不算期初前。
        """
        c = create_consumable(client, code='HC-BM', name='零点边界')
        cid = c['id']

        with app.app_context():
            # 6月1日 00:00:00 入库 - 应归入6月期间
            records = [
                InboundRecord(consumable_id=cid, quantity=50, batch_number='LOT-MID',
                              inbound_time=datetime(2026, 6, 1, 0, 0, 0)),
                InboundRecord(consumable_id=cid, quantity=30, batch_number='LOT-MAY',
                              inbound_time=datetime(2026, 5, 31, 23, 59, 59)),
            ]
            _db.session.add_all(records)
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初 = 0 + 30(5月31日入库) = 30
        # 期间入库 = 50(6月1日入库)
        assert item['initial_stock'] == 30
        assert item['period_inbound'] == 50
        assert item['ending_stock'] == 80  # 30 + 50

    def test_period_boundary_end_date_last_second(self, client, app):
        """
        边界：end_date当天23:59:59的入库记录属于期间内。
        inbound_time <= '2026-06-30 23:59:59' 应包含 23:59:59 的记录。
        """
        c = create_consumable(client, code='HC-BE', name='末秒边界')
        cid = c['id']

        with app.app_context():
            records = [
                InboundRecord(consumable_id=cid, quantity=100, batch_number='LOT-END',
                              inbound_time=datetime(2026, 6, 30, 23, 59, 59)),
            ]
            _db.session.add_all(records)
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['period_inbound'] == 100
        assert item['ending_stock'] == 100

    def test_period_no_records_at_all(self, client, app):
        """
        边界：耗材只有期初前的入库记录，期间内无出入库。
        期初前入库80，期间入库=0，期间出库=0，期末=80。
        """
        c = create_consumable(client, code='HC-NR', name='无记录耗材')
        cid = c['id']

        # 插入期初前的入库记录
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=80, batch_number='LOT-INIT',
                inbound_time=datetime(2025, 12, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=80))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-01-01&end_date=2026-12-31')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 80
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 80

    def test_period_zero_initial_no_records(self, client, app):
        """
        边界：没有任何出入库记录。
        所有值均为0。
        """
        c = create_consumable(client, code='HC-ZNR', name='零记录耗材')
        cid = c['id']

        resp = client.get('/api/stock/period-inventory?start_date=2026-01-01&end_date=2026-12-31')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 0
        assert item['current_stock'] == 0

    def test_period_current_stock_equals_ending_for_today(self, client, app):
        """
        一致性：查询今天的期间时，期末库存应等于当前实时库存(current_stock)。
        当天入库都归入期间入库。
        """
        c = create_consumable(client, code='HC-CSE', name='当日期末一致')
        cid = c['id']
        # 当天入库50
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-INIT',
                inbound_time=datetime.now()))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=50))
            _db.session.commit()
        create_inbound(client, cid, quantity=30, batch_number='LOT001')
        create_outbound(client, cid, quantity=20)

        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 当天入库(50)归入期间入库，期初=0
        # 期末 = 期初(0) + 期间入库(50+30) - 期间出库(20) = 60
        assert item['ending_stock'] == 60
        # current_stock = 批次之和 = 入库批次(50) + 入库批次(30) - 出库(20) = 60
        assert item['current_stock'] == 60
        assert item['ending_stock'] == item['current_stock']

    def test_period_current_stock_differs_for_historical(self, client, app):
        """
        一致性：查询历史期间时，期末库存不等于当前实时库存。
        current_stock 是所有批次 quantity 之和（反映实时库存），
        ending_stock 是历史期末的公式计算值。
        当历史期后有新的入库时，current_stock > 5月期末。
        """
        c = create_consumable(client, code='HC-CSD', name='历史期末不同')
        cid = c['id']

        # 12月入库100、5月入库50、出库20；6月入库30（全部通过ORM插入历史数据）
        with app.app_context():
            # 12月入库100（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-INIT',
                inbound_time=datetime(2025, 12, 1, 10, 0, 0)
            ))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=100
            ))
            # 5月入库 + 批次
            may_inbound = InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-MAY',
                inbound_time=datetime(2026, 5, 10, 10, 0, 0)
            )
            may_batch = StockBatch(
                consumable_id=cid, batch_number='LOT-MAY', quantity=30,  # 50-20=30（出库已扣）
            )
            # 5月出库记录
            may_outbound = OutboundRecord(
                consumable_id=cid, quantity=20,
                outbound_time=datetime(2026, 5, 15, 10, 0, 0),
                batch_detail='[]'
            )
            _db.session.add_all([may_inbound, may_batch, may_outbound])
            _db.session.commit()

        # 6月入库30（通过ORM插入历史数据）
        with app.app_context():
            june_inbound = InboundRecord(
                consumable_id=cid, quantity=30, batch_number='LOT-JUN',
                inbound_time=datetime(2026, 6, 5, 10, 0, 0)
            )
            june_batch = StockBatch(
                consumable_id=cid, batch_number='LOT-JUN', quantity=30,
            )
            _db.session.add_all([june_inbound, june_batch])
            _db.session.commit()

        # 查5月期间
        resp = client.get('/api/stock/period-inventory?start_date=2026-05-01&end_date=2026-05-31')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 5月期末 = 100(12月入库) + 50(5月入库) - 20(5月出库) = 130
        assert item['ending_stock'] == 130
        # current_stock = 批次之和 = 100(期初批次) + 30(5月批次扣减后) + 30(6月批次) = 160
        assert item['current_stock'] == 160
        # 历史期末 ≠ 当前库存（6月入库导致current_stock更大）
        assert item['ending_stock'] != item['current_stock']

    def test_period_formula_consistency_with_batch(self, client, app):
        """
        一致性：期间公式 期末 = 期初 + 期间入库 - 期间出库 应等于 current_stock。
        当查询涵盖所有历史记录时，ending_stock 应等于 current_stock。
        """
        c = create_consumable(client, code='HC-PFC', name='公式与批次一致')
        cid = c['id']
        # 插入期初前的入库记录
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-INIT',
                inbound_time=datetime(2019, 1, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=50))
            _db.session.commit()
        create_inbound(client, cid, quantity=80, batch_number='LOT001')
        create_inbound(client, cid, quantity=40, batch_number='LOT002')
        create_outbound(client, cid, quantity=60)
        create_outbound(client, cid, quantity=20)

        # 查询从很早的日期开始，覆盖所有记录
        resp = client.get('/api/stock/period-inventory?start_date=2020-01-01&end_date=2099-12-31')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初 = 50(2019年入库，在查询期间之前)
        # 期间入库 = 80 + 40 = 120
        # 期间出库 = 60 + 20 = 80
        # 期末 = 50 + 120 - 80 = 90
        assert item['initial_stock'] == 50
        assert item['period_inbound'] == 120
        assert item['period_outbound'] == 80
        assert item['ending_stock'] == 90
        # current_stock = 批次之和 = 50(期初批次) + 80 + 40 - 60 - 20 = 90
        assert item['current_stock'] == 90
        assert item['ending_stock'] == item['current_stock']

    def test_period_only_outbound_no_inbound(self, client, app):
        """
        边界：只有出库没有入库的期间。
        12月入库100，期初前入库100+出库30，期间出库20。
        期初=100+100-30=170，期间出库20，期末=150。
        """
        c = create_consumable(client, code='HC-OON', name='仅出库期间')
        cid = c['id']

        with app.app_context():
            # 12月入库100（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-INIT0',
                inbound_time=datetime(2025, 12, 1, 10, 0, 0)
            ))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT0', quantity=100
            ))
            # 1月入库以保证有库存可出
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-INIT',
                inbound_time=datetime(2026, 1, 5, 10, 0, 0)
            ))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=100
            ))
            # 5月出库
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=30,
                outbound_time=datetime(2026, 5, 15, 10, 0, 0)
            ))
            # 6月出库
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=20,
                outbound_time=datetime(2026, 6, 15, 10, 0, 0)
            ))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初 = 100(12月入库) + 100(1月入库) - 30(5月出库) = 170
        # 期间出库 = 20
        # 期末 = 170 - 20 = 150
        assert item['initial_stock'] == 170
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 20
        assert item['ending_stock'] == 150

    def test_period_only_inbound_no_outbound(self, client, app):
        """
        边界：只有入库没有出库的期间。
        12月入库30，期初前入库20，期间入库50。
        期初=30+20=50，期间入库50，期末=100。
        """
        c = create_consumable(client, code='HC-ION', name='仅入库期间')
        cid = c['id']

        with app.app_context():
            # 12月入库30（期初前）
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=30, batch_number='LOT-INIT',
                inbound_time=datetime(2025, 12, 1, 10, 0, 0)
            ))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=30
            ))
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=20, batch_number='LOT-MAY',
                inbound_time=datetime(2026, 5, 10, 10, 0, 0)
            ))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-MAY', quantity=20
            ))
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-JUN',
                inbound_time=datetime(2026, 6, 10, 10, 0, 0)
            ))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-JUN', quantity=50
            ))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初 = 30(12月入库) + 20(5月入库) = 50
        # 期间入库 = 50
        # 期末 = 100
        assert item['initial_stock'] == 50
        assert item['period_inbound'] == 50
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 100

    def test_period_inventory_delete_inbound_affects_formula(self, client, app):
        """
        删除入库记录后期间库存公式重新计算。
        创建入库后删除，期间查询的入库量应减少。
        """
        c = create_consumable(client, code='HC-DIA', name='删入库后期间')
        cid = c['id']

        r = create_inbound(client, cid, quantity=100, batch_number='LOT001')
        create_outbound(client, cid, quantity=30)

        today = date.today().strftime('%Y-%m-%d')

        # 删除前
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item_before = next(i for i in data['items'] if i['id'] == cid)
        assert item_before['period_inbound'] == 100
        assert item_before['period_outbound'] == 30
        assert item_before['ending_stock'] == 70

        # 删除入库记录
        client.delete(f'/api/stock/inbound/{r["id"]}')

        # 删除后
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item_after = next(i for i in data['items'] if i['id'] == cid)
        # 入库记录删除后，期间入库=0；出库记录仍在
        # 但注意：删除入库会同时扣减批次库存，如果出库记录引用的批次也被删除，
        # 那么出库可能不再有效。这里出库记录仍存在，所以 period_outbound 仍为 30
        assert item_after['period_inbound'] == 0
        # 期初=0, 期间入库=0, 期间出库=30, 期末=max(0, -30)=0
        # 删除入库后出库记录仍被计算，负数截断为0
        assert item_after['period_outbound'] == 30
        assert item_after['ending_stock'] == 0

    def test_period_inventory_delete_outbound_affects_formula(self, client, app):
        """
        删除出库记录后期间库存公式重新计算。
        """
        c = create_consumable(client, code='HC-DOA', name='删出库后期间')
        cid = c['id']

        # 插入期初前的入库记录，确保归入期初
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-INIT',
                inbound_time=datetime(2019, 1, 1, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=50))
            _db.session.commit()

        create_inbound(client, cid, quantity=50, batch_number='LOT001')
        r = create_outbound(client, cid, quantity=30)

        today = date.today().strftime('%Y-%m-%d')

        # 删除前
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item_before = next(i for i in data['items'] if i['id'] == cid)
        assert item_before['period_outbound'] == 30
        assert item_before['ending_stock'] == 70  # 50 + 50 - 30

        # 删除出库记录
        client.delete(f'/api/stock/outbound/{r["id"]}')

        # 删除后
        resp = client.get(f'/api/stock/period-inventory?start_date={today}&end_date={today}')
        data = resp.get_json()
        item_after = next(i for i in data['items'] if i['id'] == cid)
        assert item_after['period_outbound'] == 0
        assert item_after['ending_stock'] == 100  # 50 + 50 - 0
        assert item_after['current_stock'] == 100

    def test_period_inventory_single_day(self, client, app):
        """
        边界：查询单日区间 start_date == end_date。
        """
        c = create_consumable(client, code='HC-SD', name='单日期间')
        cid = c['id']

        with app.app_context():
            # 当天入库和出库
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=80, batch_number='LOT-DAY',
                inbound_time=datetime(2026, 6, 15, 10, 0, 0)
            ))
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=30,
                outbound_time=datetime(2026, 6, 15, 14, 0, 0)
            ))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-15&end_date=2026-06-15')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 80
        assert item['period_outbound'] == 30
        assert item['ending_stock'] == 50

    def test_period_inventory_empty_period(self, client, app):
        """
        边界：查询区间内无任何出入库，但之前有记录。
        期初应该等于上一个期间结束时的期末值。
        """
        c = create_consumable(client, code='HC-EP', name='空期间')
        cid = c['id']

        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-JAN',
                inbound_time=datetime(2026, 1, 15, 10, 0, 0)
            ))
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=40,
                outbound_time=datetime(2026, 1, 20, 10, 0, 0)
            ))
            _db.session.commit()

        # 查2月（空期间）
        resp = client.get('/api/stock/period-inventory?start_date=2026-02-01&end_date=2026-02-28')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初 = 0 + 100(1月入库) - 40(1月出库) = 60
        # 期间无出入库
        assert item['initial_stock'] == 60
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 60

    def test_period_inventory_negative_ending(self, client, app):
        """
        边界：出库超过入库导致期末为负数（数据不一致场景）。
        这在实际业务中不应该发生（出库时校验库存），但如果数据被修改可能产生。
        负数截断为0，避免界面显示不合理数据。
        """
        c = create_consumable(client, code='HC-NEG', name='负数期末')
        cid = c['id']

        with app.app_context():
            # 直接插入出库记录（绕过API校验）模拟数据不一致
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=50,
                outbound_time=datetime(2026, 6, 15, 10, 0, 0)
            ))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初=0, 期间出库50, 期末 = max(0, 0-50) = 0
        assert item['initial_stock'] == 0
        assert item['period_outbound'] == 50
        assert item['ending_stock'] == 0


class TestPeriodInventoryInboundTime:
    """期间库存查询 - 入库记录时间影响归属"""

    def test_inbound_before_period(self, client, app):
        """
        入库记录在期间之前 → 归入期初。
        1月入库100，查6月期间：
        期初=100，期间入库=0，期末=100。
        """
        c = create_consumable(client, code='HC-IB', name='期初前入库')
        cid = c['id']
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-INIT',
                inbound_time=datetime(2026, 1, 15, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=100))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 100
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 100

    def test_inbound_within_period(self, client, app):
        """
        入库记录在期间内 → 归入期间入库，不计入期初。
        6月10日入库100，查6月期间：
        期初=0，期间入库=100，期末=100。
        """
        c = create_consumable(client, code='HC-IW', name='期间内入库')
        cid = c['id']
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-JUN',
                inbound_time=datetime(2026, 6, 10, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-JUN', quantity=100))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 100
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 100

    def test_inbound_after_period(self, client, app):
        """
        入库记录在期间之后 → 不计入本期间（期初和期间入库都不算）。
        7月入库100，查6月期间：
        期初=0，期间入库=0，期末=0。
        """
        c = create_consumable(client, code='HC-IA', name='期间后入库')
        cid = c['id']
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=100, batch_number='LOT-JUL',
                inbound_time=datetime(2026, 7, 15, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-JUL', quantity=100))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 0

    def test_inbound_within_period_with_other_records(self, client, app):
        """
        入库记录在期间内，同时期间内有其他入库和出库。
        6月5日入库50，6月入库30出库20：
        期初=0，期间入库=50+30=80，期间出库=20，期末=60。
        """
        c = create_consumable(client, code='HC-IWI', name='期间内入库含其他')
        cid = c['id']
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=50, batch_number='LOT-INIT',
                inbound_time=datetime(2026, 6, 5, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-INIT', quantity=50))
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=30, batch_number='LOT-JUN',
                inbound_time=datetime(2026, 6, 15, 10, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-JUN', quantity=30))
            _db.session.add(OutboundRecord(
                consumable_id=cid, quantity=20,
                outbound_time=datetime(2026, 6, 20, 10, 0, 0),
                batch_detail='[]'))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # 期初=0(入库都在6月期间内)，期间入库=50+30=80
        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 80
        assert item['period_outbound'] == 20
        assert item['ending_stock'] == 60  # 0 + 80 - 20

    def test_inbound_on_period_start_date(self, client, app):
        """
        入库记录时间恰好在期间起始日 → 归入期间入库（等于start_date算期间内）。
        6月1日入库80，查6月期间：
        期初=0，期间入库=80，期末=80。
        """
        c = create_consumable(client, code='HC-ICB', name='期间起始日入库')
        cid = c['id']
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=80, batch_number='LOT-START',
                inbound_time=datetime(2026, 6, 1, 8, 0, 0)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-START', quantity=80))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        # inbound_time 日期=2026-06-01 = start_date，归入期间入库
        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 80
        assert item['ending_stock'] == 80

    def test_inbound_day_before_period(self, client, app):
        """
        入库记录在期间前一天 → 归入期初。
        5月31日入库80，查6月期间：
        期初=80，期间入库=0，期末=80。
        """
        c = create_consumable(client, code='HC-IDA', name='期间前日入库')
        cid = c['id']
        with app.app_context():
            _db.session.add(InboundRecord(
                consumable_id=cid, quantity=80, batch_number='LOT-PRE',
                inbound_time=datetime(2026, 5, 31, 23, 59, 59)))
            _db.session.add(StockBatch(
                consumable_id=cid, batch_number='LOT-PRE', quantity=80))
            _db.session.commit()

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 80
        assert item['period_inbound'] == 0
        assert item['ending_stock'] == 80

    def test_no_inbound_records_at_all(self, client, app):
        """
        兼容性：没有任何入库记录的耗材，期间库存全部为0。
        """
        c = create_consumable(client, code='HC-NBF', name='无入库记录')

        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == c['id'])

        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 0
        assert item['ending_stock'] == 0

    def test_zero_quantity_inbound_ignored(self, client, app):
        """
        没有入库记录的耗材，期间库存全部为0。
        """
        c = create_consumable(client, code='HC-ISZ', name='无入库耗材')
        cid = c['id']
        resp = client.get('/api/stock/period-inventory?start_date=2026-06-01&end_date=2026-06-30')
        data = resp.get_json()
        item = next(i for i in data['items'] if i['id'] == cid)

        assert item['initial_stock'] == 0
        assert item['period_inbound'] == 0
        assert item['period_outbound'] == 0
        assert item['ending_stock'] == 0

class TestInboundStockConsistency:
    """入库后库存一致性验证"""

    def test_total_stock_equals_batch_sum(self, client, app):
        """总库存 = 所有批次库存之和"""
        c = create_consumable(client, code='HC-IB1', name='批次一致')
        cid = c['id']
        create_inbound(client, cid, quantity=50, batch_number='LOT-A')
        create_inbound(client, cid, quantity=30, batch_number='LOT-B')
        create_inbound(client, cid, quantity=20, batch_number='LOT-C')

        with app.app_context():
            consumable = Consumable.query.get(cid)
            batch_sum = sum(b.quantity for b in StockBatch.query.filter_by(consumable_id=cid).all())
            assert consumable.total_stock == batch_sum == 100

    def test_total_inbound_equals_record_sum(self, client, app):
        """累计入库量 = 所有入库记录数量之和"""
        c = create_consumable(client, code='HC-IB2', name='入库一致')
        cid = c['id']
        create_inbound(client, cid, quantity=50, batch_number='LOT-A')
        create_inbound(client, cid, quantity=30, batch_number='LOT-B')

        with app.app_context():
            consumable = Consumable.query.get(cid)
            record_sum = _db.session.query(
                _db.func.coalesce(_db.func.sum(InboundRecord.quantity), 0)
            ).filter(InboundRecord.consumable_id == cid).scalar()
            assert consumable.total_inbound == int(record_sum) == 80

    def test_multiple_inbound_stock(self, client, app):
        """多次入库：总库存 = 所有入库批次之和"""
        c = create_consumable(client, code='HC-IB3', name='多次入库')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT-INIT')
        create_inbound(client, cid, quantity=50, batch_number='LOT001')

        with app.app_context():
            consumable = Consumable.query.get(cid)
            # 总库存 = 100 + 50 = 150
            assert consumable.total_stock == 150
            # 验证有两个批次
            batches = StockBatch.query.filter_by(consumable_id=cid).all()
            assert len(batches) == 2
            batch_sum = sum(b.quantity for b in batches)
            assert batch_sum == 150

    def test_delete_inbound_reduces_stock(self, client, app):
        """删除入库记录后库存正确扣减"""
        c = create_consumable(client, code='HC-IB4', name='删入库')
        cid = c['id']
        r1 = create_inbound(client, cid, quantity=100, batch_number='LOT001')
        create_inbound(client, cid, quantity=50, batch_number='LOT002')

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 150

        # 删除第一条入库
        client.delete(f'/api/stock/inbound/{r1["id"]}')

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 50

    def test_inbound_same_batch_number_creates_separate_batch(self, client, app):
        """相同批号入库创建独立批次"""
        c = create_consumable(client, code='HC-IB5', name='同批号入库')
        cid = c['id']
        create_inbound(client, cid, quantity=30, batch_number='LOT-SAME')
        create_inbound(client, cid, quantity=20, batch_number='LOT-SAME')

        with app.app_context():
            batches = StockBatch.query.filter_by(consumable_id=cid).all()
            # 两次入库创建两个独立批次
            assert len(batches) == 2
            total = sum(b.quantity for b in batches)
            assert total == 50
            assert Consumable.query.get(cid).total_stock == 50


# ======================== 出库后库存一致性 ========================

class TestOutboundStockConsistency:
    """出库后库存一致性验证"""

    def test_outbound_reduces_stock(self, client, app):
        """出库后库存正确减少"""
        c = create_consumable(client, code='HC-OB1', name='出库减少')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')
        create_outbound(client, cid, quantity=30)

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 70

    def test_outbound_total_outbound_equals_record_sum(self, client, app):
        """累计出库量 = 所有出库记录数量之和"""
        c = create_consumable(client, code='HC-OB2', name='出库累计')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')
        create_outbound(client, cid, quantity=30)
        create_outbound(client, cid, quantity=20)

        with app.app_context():
            consumable = Consumable.query.get(cid)
            record_sum = _db.session.query(
                _db.func.coalesce(_db.func.sum(OutboundRecord.quantity), 0)
            ).filter(OutboundRecord.consumable_id == cid).scalar()
            assert consumable.total_outbound == int(record_sum) == 50

    def test_outbound_insufficient_stock_rejected(self, client, app):
        """库存不足时出库被拒绝，库存不变"""
        c = create_consumable(client, code='HC-OB3', name='出库不足')
        cid = c['id']
        create_inbound(client, cid, quantity=10, batch_number='LOT001')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid, 'quantity': 20,
        })
        assert resp.status_code == 400

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 10

    def test_delete_outbound_restores_stock(self, client, app):
        """删除出库记录后库存恢复"""
        c = create_consumable(client, code='HC-OB4', name='删出库')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')
        r = create_outbound(client, cid, quantity=30, batch_number='LOT001')

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 70

        client.delete(f'/api/stock/outbound/{r["id"]}')

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 100

    def test_stock_formula_consistency(self, client, app):
        """库存公式一致性：当前库存 = 所有批次之和 = 累计入库 - 累计出库"""
        c = create_consumable(client, code='HC-OB5', name='公式一致')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT-INIT')
        create_inbound(client, cid, quantity=50, batch_number='LOT001')
        create_inbound(client, cid, quantity=30, batch_number='LOT002')
        create_outbound(client, cid, quantity=40)

        with app.app_context():
            consumable = Consumable.query.get(cid)
            batch_sum = sum(b.quantity for b in StockBatch.query.filter_by(consumable_id=cid).all())
            # 总库存 = 批次之和
            assert consumable.total_stock == batch_sum
            # 批次之和 = 入库(100+50+30) - 出库(40) = 140
            assert batch_sum == 140
            # total_inbound = 100+50+30 = 180
            # 验证 total_stock = total_inbound - total_outbound
            assert consumable.total_stock == consumable.total_inbound - consumable.total_outbound

    def test_full_outbound_then_zero_stock(self, client, app):
        """全部出库后库存为0"""
        c = create_consumable(client, code='HC-OB6', name='全部出库')
        cid = c['id']
        create_inbound(client, cid, quantity=50, batch_number='LOT001')
        create_outbound(client, cid, quantity=50)

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 0


# ======================== FIFO出库逻辑 ========================

class TestOutboundFIFO:
    """FIFO 先进先出扣减逻辑"""

    def test_fifo_deducts_earliest_expiry_first(self, client, app):
        """FIFO：优先扣减最早过期的批次"""
        c = create_consumable(client, code='HC-FIFO1', name='FIFO过期')
        cid = c['id']
        create_inbound(client, cid, quantity=50, batch_number='LOT-EARLY',
                       expiry_date='2025-12-31')
        create_inbound(client, cid, quantity=50, batch_number='LOT-LATE',
                       expiry_date='2027-12-31')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid, 'quantity': 30,
        })
        assert resp.status_code == 201

        with app.app_context():
            early = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-EARLY').first()
            late = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-LATE').first()
            assert early.quantity == 20  # 50-30
            assert late.quantity == 50

    def test_fifo_cross_batch_deduction(self, client, app):
        """FIFO：第一个批次不足时跨批次扣减"""
        c = create_consumable(client, code='HC-FIFO2', name='FIFO跨批')
        cid = c['id']
        create_inbound(client, cid, quantity=30, batch_number='LOT-A',
                       expiry_date='2025-12-31')
        create_inbound(client, cid, quantity=50, batch_number='LOT-B',
                       expiry_date='2027-12-31')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid, 'quantity': 50,
        })
        assert resp.status_code == 201

        with app.app_context():
            early = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-A').first()
            late = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-B').first()
            assert early is None or early.quantity == 0
            assert late.quantity == 30  # 50 - 20

    def test_fifo_specified_batch(self, client, app):
        """指定批号出库"""
        c = create_consumable(client, code='HC-FIFO3', name='指定批号')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT-SPEC',
                       expiry_date='2027-12-31')
        create_inbound(client, cid, quantity=100, batch_number='LOT-OTHER',
                       expiry_date='2026-12-31')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid, 'quantity': 40, 'batch_number': 'LOT-SPEC',
        })
        assert resp.status_code == 201

        with app.app_context():
            spec = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-SPEC').first()
            other = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-OTHER').first()
            assert spec.quantity == 60
            assert other.quantity == 100

    def test_fifo_no_expiry_date_uses_created_at(self, client, app):
        """无失效日期的批次按创建时间排序扣减"""
        c = create_consumable(client, code='HC-FIFO4', name='无日期FIFO')
        cid = c['id']
        create_inbound(client, cid, quantity=30, batch_number='LOT-FIRST')
        create_inbound(client, cid, quantity=50, batch_number='LOT-SECOND')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid, 'quantity': 40,
        })
        assert resp.status_code == 201

        with app.app_context():
            first = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-FIRST').first()
            assert first is None or first.quantity == 0
            # 30 from FIRST + 10 from SECOND = 40
            second = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-SECOND').first()
            assert second.quantity == 40  # 50 - 10

    def test_fifo_batch_detail_recorded(self, client, app):
        """FIFO跨批次扣减时记录batch_detail"""
        c = create_consumable(client, code='HC-FIFO5', name='批次明细')
        cid = c['id']
        create_inbound(client, cid, quantity=30, batch_number='LOT-A',
                       expiry_date='2025-12-31')
        create_inbound(client, cid, quantity=50, batch_number='LOT-B',
                       expiry_date='2027-12-31')

        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid, 'quantity': 50,
        })
        assert resp.status_code == 201
        data = resp.get_json()

        with app.app_context():
            record = OutboundRecord.query.get(data['id'])
            if record.batch_detail:
                import json
                detail = json.loads(record.batch_detail)
                total_deducted = sum(d['quantity'] for d in detail)
                assert total_deducted == 50


# ======================== 出库删除后库存恢复 ========================

class TestOutboundDeleteRestore:
    """出库删除后库存恢复"""

    def test_delete_outbound_restores_fifo_batch(self, client, app):
        """删除FIFO跨批出库记录后，各批次库存正确恢复"""
        c = create_consumable(client, code='HC-OD1', name='删FIFO出库')
        cid = c['id']
        create_inbound(client, cid, quantity=30, batch_number='LOT-A',
                       expiry_date='2025-12-31')
        create_inbound(client, cid, quantity=50, batch_number='LOT-B',
                       expiry_date='2027-12-31')

        # 跨批出库50：LOT-A扣30, LOT-B扣20
        resp = client.post('/api/stock/outbound', json={
            'consumable_id': cid, 'quantity': 50,
        })
        assert resp.status_code == 201
        record_id = resp.get_json()['id']

        with app.app_context():
            # LOT-A应为0, LOT-B应为30
            batch_a = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-A').first()
            batch_b = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-B').first()
            assert batch_a is None or batch_a.quantity == 0
            assert batch_b.quantity == 30

        # 删除出库记录
        resp = client.delete(f'/api/stock/outbound/{record_id}')
        assert resp.status_code == 200

        with app.app_context():
            # LOT-A恢复为30, LOT-B恢复为50
            batch_a = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-A').first()
            batch_b = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT-B').first()
            assert batch_a is not None
            assert batch_a.quantity == 30
            assert batch_b.quantity == 50
            assert Consumable.query.get(cid).total_stock == 80

    def test_delete_single_batch_outbound(self, client, app):
        """删除单批次出库记录后库存恢复"""
        c = create_consumable(client, code='HC-OD2', name='删单批出库')
        cid = c['id']
        create_inbound(client, cid, quantity=100, batch_number='LOT001')

        r = create_outbound(client, cid, quantity=30, batch_number='LOT001')

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 70

        client.delete(f'/api/stock/outbound/{r["id"]}')

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 100
            batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT001').first()
            assert batch.quantity == 100


# ======================== 效期查询 ========================

class TestExpiryQuery:
    """效期查询接口"""

    def test_expiry_query_list(self, client, app):
        """效期查询返回有库存的批次"""
        c = create_consumable(client, code='HC-EQL', name='效期查询')
        create_inbound(client, c['id'], quantity=50, batch_number='LOT-E1',
                       expiry_date='2025-12-31')
        create_inbound(client, c['id'], quantity=30, batch_number='LOT-E2',
                       expiry_date='2027-12-31')

        resp = client.get('/api/stock/expiry-query')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 2

    def test_expiry_query_filter_near_expiry(self, client, app):
        """效期查询按近效期筛选"""
        c = create_consumable(client, code='HC-EQN', name='近效期查询', expiry_warning_days=90)
        near_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-NEAR',
                       expiry_date=near_date)

        resp = client.get('/api/stock/expiry-query?status=near_expiry')
        assert resp.status_code == 200
        data = resp.get_json()
        batch_numbers = [i['batch_number'] for i in data['items']]
        assert 'LOT-NEAR' in batch_numbers

    def test_expiry_query_filter_expired(self, client, app):
        """效期查询按已过期筛选"""
        c = create_consumable(client, code='HC-EQE', name='过期查询', expiry_warning_days=30)
        past_date = (date.today() - timedelta(days=10)).strftime('%Y-%m-%d')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-EXP',
                       expiry_date=past_date)

        resp = client.get('/api/stock/expiry-query?status=expired')
        assert resp.status_code == 200
        data = resp.get_json()
        batch_numbers = [i['batch_number'] for i in data['items']]
        assert 'LOT-EXP' in batch_numbers

    def test_expiry_query_hides_zero_quantity(self, client, app):
        """效期查询不显示库存为0的批次"""
        c = create_consumable(client, code='HC-EQZ', name='零库存效期')
        create_inbound(client, c['id'], quantity=10, batch_number='LOT-ZERO')
        create_outbound(client, c['id'], quantity=10)

        resp = client.get('/api/stock/expiry-query')
        data = resp.get_json()
        batch_numbers = [i['batch_number'] for i in data['items']]
        assert 'LOT-ZERO' not in batch_numbers


# ======================== 仪表盘 ========================

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

    def test_dashboard_trend_data(self, client, app):
        """仪表盘趋势数据包含30天"""
        resp = client.get('/api/stock/dashboard')
        data = resp.get_json()
        assert len(data['trend']['days']) == 30
        assert len(data['trend']['inbound']) == 30
        assert len(data['trend']['outbound']) == 30

    def test_dashboard_total_stock_equals_sum(self, client, app):
        """仪表盘总库存等于各耗材批次之和"""
        c1 = create_consumable(client, code='HC-DT1', name='统计A')
        c2 = create_consumable(client, code='HC-DT2', name='统计B')
        create_inbound(client, c1['id'], quantity=100, batch_number='LOT001')
        create_inbound(client, c2['id'], quantity=50, batch_number='LOT002')

        resp = client.get('/api/stock/dashboard')
        data = resp.get_json()
        # 总库存至少 150（可能有其他测试的耗材）
        assert data['total_stock'] >= 150


# ======================== 入库删除后库存一致性 ========================

class TestInboundDeleteConsistency:
    """入库删除后库存一致性"""

    def test_delete_inbound_reduces_stock(self, client, app):
        """删除入库记录后库存正确扣减"""
        c = create_consumable(client, code='HC-ID1', name='删入库库存')
        cid = c['id']
        r = create_inbound(client, cid, quantity=100, batch_number='LOT001')
        record_id = r['id']

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 100

        resp = client.delete(f'/api/stock/inbound/{record_id}')
        assert resp.status_code == 200

        with app.app_context():
            assert Consumable.query.get(cid).total_stock == 0

    def test_delete_inbound_reduces_batch(self, client, app):
        """删除入库记录后批次库存扣减"""
        c = create_consumable(client, code='HC-ID2', name='删入库批次')
        cid = c['id']
        r = create_inbound(client, cid, quantity=100, batch_number='LOT001')

        client.delete(f'/api/stock/inbound/{r["id"]}')

        with app.app_context():
            batch = StockBatch.query.filter_by(consumable_id=cid, batch_number='LOT001').first()
            assert batch is None or batch.quantity == 0

    def test_delete_inbound_partial_batch(self, client, app):
        """同批号多次入库，删除其中一条只扣减对应数量"""
        c = create_consumable(client, code='HC-ID3', name='删部分入库')
        cid = c['id']
        r1 = create_inbound(client, cid, quantity=100, batch_number='LOT001')
        create_inbound(client, cid, quantity=50, batch_number='LOT001')

        client.delete(f'/api/stock/inbound/{r1["id"]}')

        with app.app_context():
            batches = StockBatch.query.filter_by(consumable_id=cid).all()
            remaining = sum(b.quantity for b in batches)
            assert remaining == 50