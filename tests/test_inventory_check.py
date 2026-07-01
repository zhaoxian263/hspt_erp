"""盘点模块测试 — 盘点确认后库存调整是否正确"""
import pytest
from datetime import date
from models import Consumable, StockBatch, InventoryCheck, InventoryCheckItem
from tests.conftest import create_consumable, create_inbound


class TestInventoryCheckCreate:
    """创建盘点"""

    def test_create_check_auto_fills_system_quantity(self, client, app):
        """创建盘点时自动填充所有耗材的系统库存数量"""
        c1 = create_consumable(client, code='HC001', name='耗材A')
        c2 = create_consumable(client, code='HC002', name='耗材B')
        create_inbound(client, c1['id'], quantity=100, batch_number='LOT001')
        create_inbound(client, c2['id'], quantity=50, batch_number='LOT002')

        resp = client.post('/api/inventory-checks', json={
            'check_date': '2025-07-01',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['status'] == 'draft'
        assert len(data['items']) == 2

        # 验证系统库存数量
        item_a = next(i for i in data['items'] if i['consumable_id'] == c1['id'])
        item_b = next(i for i in data['items'] if i['consumable_id'] == c2['id'])
        assert item_a['system_quantity'] == 100
        assert item_b['system_quantity'] == 50

    def test_create_check_default_date(self, client, app):
        """不指定盘点日期时默认使用当天"""
        c = create_consumable(client)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        resp = client.post('/api/inventory-checks', json={})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['check_date'] == date.today().strftime('%Y-%m-%d')


class TestInventoryCheckUpdate:
    """更新盘点明细"""

    def test_update_actual_quantity(self, client, app):
        """录入实盘数量后自动计算盈亏"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        # 创建盘点
        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']

        # 找到该耗材的盘点项
        item = next(i for i in check['items'] if i['consumable_id'] == c['id'])
        assert item['system_quantity'] == 100
        assert item['actual_quantity'] is None

        # 录入实盘数量
        resp = client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [
                {'id': item['id'], 'actual_quantity': 95}
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        updated_item = next(i for i in data['items'] if i['consumable_id'] == c['id'])
        assert updated_item['actual_quantity'] == 95
        assert updated_item['difference'] == -5  # 95 - 100

    def test_update_multiple_items(self, client, app):
        """批量更新多条盘点项"""
        c1 = create_consumable(client, code='HC001', name='耗材A')
        c2 = create_consumable(client, code='HC002', name='耗材B')
        create_inbound(client, c1['id'], quantity=100, batch_number='LOT001')
        create_inbound(client, c2['id'], quantity=50, batch_number='LOT002')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']

        item_a = next(i for i in check['items'] if i['consumable_id'] == c1['id'])
        item_b = next(i for i in check['items'] if i['consumable_id'] == c2['id'])

        resp = client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [
                {'id': item_a['id'], 'actual_quantity': 90},   # 亏10
                {'id': item_b['id'], 'actual_quantity': 55},   # 盘5
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        updated_a = next(i for i in data['items'] if i['consumable_id'] == c1['id'])
        updated_b = next(i for i in data['items'] if i['consumable_id'] == c2['id'])
        assert updated_a['difference'] == -10
        assert updated_b['difference'] == 5

    def test_cannot_update_confirmed_check(self, client, app):
        """已确认的盘点不能修改"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']

        item = next(i for i in check['items'] if i['consumable_id'] == c['id'])

        # 录入实盘数量并确认
        client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [{'id': item['id'], 'actual_quantity': 100}]
        })
        client.post(f'/api/inventory-checks/{check_id}/confirm')

        # 尝试修改已确认的盘点
        resp = client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [{'id': item['id'], 'actual_quantity': 50}]
        })
        assert resp.status_code == 400


class TestInventoryCheckConfirm:
    """确认盘点并调整库存"""

    def test_confirm_adjusts_stock_shortage(self, client, app):
        """盘点确认：盘亏时库存减少"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']
        item = next(i for i in check['items'] if i['consumable_id'] == c['id'])

        # 实盘数量为 90，亏 10
        client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [{'id': item['id'], 'actual_quantity': 90}]
        })

        resp = client.post(f'/api/inventory-checks/{check_id}/confirm')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'confirmed'

        # 验证库存已调整
        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.total_stock == 90

    def test_confirm_adjusts_stock_surplus(self, client, app):
        """盘点确认：盘盈时库存增加"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']
        item = next(i for i in check['items'] if i['consumable_id'] == c['id'])

        # 实盘数量为 110，盈 10
        client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [{'id': item['id'], 'actual_quantity': 110}]
        })

        resp = client.post(f'/api/inventory-checks/{check_id}/confirm')
        assert resp.status_code == 200

        # 验证库存已调整
        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.total_stock == 110

            # 验证盘盈批次
            surplus_batch = StockBatch.query.filter_by(
                consumable_id=c['id'], batch_number='盘盈调整'
            ).first()
            assert surplus_batch is not None
            assert surplus_batch.quantity == 10

    def test_confirm_with_zero_difference_no_change(self, client, app):
        """盘点确认：盈亏为0时不调整库存"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']
        item = next(i for i in check['items'] if i['consumable_id'] == c['id'])

        # 实盘数量 = 系统数量
        client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [{'id': item['id'], 'actual_quantity': 100}]
        })

        client.post(f'/api/inventory-checks/{check_id}/confirm')

        with app.app_context():
            consumable = Consumable.query.get(c['id'])
            assert consumable.total_stock == 100

    def test_cannot_confirm_with_unfilled_items(self, client, app):
        """有未录入实盘数量的记录时不能确认"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']

        # 直接确认，不录入实盘数量
        resp = client.post(f'/api/inventory-checks/{check_id}/confirm')
        assert resp.status_code == 400
        assert '未录入' in resp.get_json()['error']

    def test_cannot_confirm_twice(self, client, app):
        """不能重复确认盘点"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']
        item = next(i for i in check['items'] if i['consumable_id'] == c['id'])

        client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [{'id': item['id'], 'actual_quantity': 100}]
        })

        client.post(f'/api/inventory-checks/{check_id}/confirm')

        # 再次确认
        resp = client.post(f'/api/inventory-checks/{check_id}/confirm')
        assert resp.status_code == 400


class TestInventoryCheckDelete:
    """删除盘点"""

    def test_delete_draft_check(self, client, app):
        """草稿状态的盘点可以删除"""
        c = create_consumable(client)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']

        resp = client.delete(f'/api/inventory-checks/{check_id}')
        assert resp.status_code == 200

    def test_cannot_delete_confirmed_check(self, client, app):
        """已确认的盘点不能删除"""
        c = create_consumable(client, code='HC001', name='耗材A')
        create_inbound(client, c['id'], quantity=100, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']
        item = next(i for i in check['items'] if i['consumable_id'] == c['id'])

        client.put(f'/api/inventory-checks/{check_id}', json={
            'items': [{'id': item['id'], 'actual_quantity': 100}]
        })
        client.post(f'/api/inventory-checks/{check_id}/confirm')

        resp = client.delete(f'/api/inventory-checks/{check_id}')
        assert resp.status_code == 400


class TestInventoryCheckList:
    """盘点列表和详情"""

    def test_list_checks(self, client, app):
        """获取盘点列表"""
        c = create_consumable(client)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        client.post('/api/inventory-checks', json={'check_date': '2025-07-01'})

        resp = client.get('/api/inventory-checks')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1

    def test_get_check_detail(self, client, app):
        """获取盘点详情"""
        c = create_consumable(client)
        create_inbound(client, c['id'], quantity=10, batch_number='LOT001')

        check = client.post('/api/inventory-checks', json={}).get_json()
        check_id = check['id']

        resp = client.get(f'/api/inventory-checks/{check_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['id'] == check_id
        assert 'items' in data
        assert len(data['items']) >= 1