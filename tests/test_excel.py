"""Excel 批量操作模块测试 — 模板下载、耗材导入/导出、入库导入、出库导出、批量修改"""
import io
import pytest
from models import Consumable, StockBatch, InboundRecord, OutboundRecord


class TestConsumableTemplate:
    """耗材导入模板下载"""

    def test_download_consumable_template(self, client, app):
        """下载耗材导入模板"""
        resp = client.get('/api/excel/template/consumable')
        assert resp.status_code == 200
        assert resp.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert len(resp.data) > 0


class TestConsumableImport:
    """耗材批量导入"""

    def _make_excel(self, headers, rows):
        """创建测试用 Excel 文件"""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def test_import_consumables(self, client, app):
        """批量导入耗材"""
        excel = self._make_excel(
            ['耗材编号', '耗材名称', '类别', '品牌名称', '规格型号', '单位', '库存预警值'],
            [
                ['IMP001', '导入耗材1', '试剂耗材', '品牌A', '100ml', '瓶', 50],
                ['IMP002', '导入耗材2', '器械耗材', '品牌B', '200ml', '盒', 30],
            ]
        )
        resp = client.post('/api/excel/import/consumable',
                           data={'file': (excel, 'test.xlsx')},
                           content_type='multipart/form-data')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] == 2
        assert len(data['errors']) == 0

        # 验证数据库
        with app.app_context():
            c1 = Consumable.query.filter_by(code='IMP001').first()
            assert c1 is not None
            assert c1.name == '导入耗材1'
            assert c1.category == '试剂耗材'

    def test_import_consumables_skip_existing(self, client, app):
        """导入耗材时跳过已有编号（skip模式）"""
        # 先创建一个耗材
        client.post('/api/consumables', json={'code': 'IMP001', 'name': '已有耗材'})

        excel = self._make_excel(
            ['耗材编号', '耗材名称'],
            [
                ['IMP001', '导入耗材1'],  # 已存在，跳过
                ['IMP002', '导入耗材2'],  # 新增
            ]
        )
        resp = client.post('/api/excel/import/consumable',
                           data={'file': (excel, 'test.xlsx'), 'mode': 'skip'},
                           content_type='multipart/form-data')
        data = resp.get_json()
        assert data['success'] == 1
        assert data['skipped'] == 1

    def test_import_consumables_update_mode(self, client, app):
        """导入耗材时更新已有编号（update模式）"""
        client.post('/api/consumables', json={'code': 'IMP001', 'name': '旧名称'})

        excel = self._make_excel(
            ['耗材编号', '耗材名称', '品牌名称'],
            [
                ['IMP001', '新名称', '新品牌'],
                ['IMP002', '导入耗材2', ''],
            ]
        )
        resp = client.post('/api/excel/import/consumable',
                           data={'file': (excel, 'test.xlsx'), 'mode': 'update'},
                           content_type='multipart/form-data')
        data = resp.get_json()
        assert data['updated'] == 1
        assert data['success'] == 1

        with app.app_context():
            c1 = Consumable.query.filter_by(code='IMP001').first()
            assert c1.name == '新名称'
            assert c1.brand == '新品牌'

    def test_import_consumables_missing_required_columns(self, client, app):
        """导入耗材缺少必填列返回400"""
        excel = self._make_excel(
            ['耗材名称'],  # 缺少耗材编号
            [['测试耗材']]
        )
        resp = client.post('/api/excel/import/consumable',
                           data={'file': (excel, 'test.xlsx')},
                           content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_import_consumables_no_file(self, client, app):
        """未上传文件返回400"""
        resp = client.post('/api/excel/import/consumable',
                           content_type='multipart/form-data')
        assert resp.status_code == 400


class TestConsumableExport:
    """耗材信息导出"""

    def test_export_consumables(self, client, app):
        """导出耗材基础信息为Excel"""
        client.post('/api/consumables', json={
            'code': 'EXP001', 'name': '导出耗材', 'category': '试剂耗材'
        })

        resp = client.get('/api/excel/export/consumable')
        assert resp.status_code == 200
        assert resp.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert len(resp.data) > 0

    def test_export_consumables_with_keyword(self, client, app):
        """按关键词导出耗材"""
        client.post('/api/consumables', json={'code': 'EXP-KW', 'name': '关键词导出耗材'})

        resp = client.get('/api/excel/export/consumable?keyword=关键词')
        assert resp.status_code == 200
        assert len(resp.data) > 0


class TestBatchUpdateConsumable:
    """批量修改耗材信息"""

    def _make_excel(self, headers, rows):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def test_batch_update_consumable(self, client, app):
        """批量修改耗材信息（按编号匹配更新）"""
        # 先创建耗材
        client.post('/api/consumables', json={'code': 'BU001', 'name': '原名', 'brand': '原品牌'})

        excel = self._make_excel(
            ['耗材编号', '耗材名称', '品牌名称'],
            [['BU001', '新名', '新品牌']]
        )
        resp = client.post('/api/excel/batch-update/consumable',
                           data={'file': (excel, 'test.xlsx')},
                           content_type='multipart/form-data')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['updated'] == 1

        with app.app_context():
            c = Consumable.query.filter_by(code='BU001').first()
            assert c.name == '新名'
            assert c.brand == '新品牌'

    def test_batch_update_skip_nonexistent(self, client, app):
        """批量修改时跳过不存在的编号"""
        excel = self._make_excel(
            ['耗材编号', '耗材名称'],
            [['NOTEXIST001', '不存在']]
        )
        resp = client.post('/api/excel/batch-update/consumable',
                           data={'file': (excel, 'test.xlsx')},
                           content_type='multipart/form-data')
        data = resp.get_json()
        assert data['skipped'] == 1
        assert data['updated'] == 0


class TestInboundImport:
    """入库记录批量导入"""

    def _make_excel(self, headers, rows):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def test_import_inbound(self, client, app):
        """批量导入入库记录"""
        # 先创建耗材
        client.post('/api/consumables', json={'code': 'IB001', 'name': '入库耗材'})

        excel = self._make_excel(
            ['耗材编号', '批号', '生产日期', '失效日期', '入库数量', '经办人'],
            [
                ['IB001', 'LOT001', '2025-01-01', '2027-01-01', 100, '张三'],
                ['IB001', 'LOT002', '2025-06-01', '2027-06-01', 50, '李四'],
            ]
        )
        resp = client.post('/api/excel/import/inbound',
                           data={'file': (excel, 'test.xlsx')},
                           content_type='multipart/form-data')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] == 2

        # 验证库存
        with app.app_context():
            c = Consumable.query.filter_by(code='IB001').first()
            assert c.total_stock == 150

    def test_import_inbound_nonexistent_consumable(self, client, app):
        """导入入库记录时耗材不存在则跳过"""
        excel = self._make_excel(
            ['耗材编号', '批号', '入库数量'],
            [['NOTEXIST', 'LOT001', 10]]
        )
        resp = client.post('/api/excel/import/inbound',
                           data={'file': (excel, 'test.xlsx')},
                           content_type='multipart/form-data')
        data = resp.get_json()
        assert data['success'] == 0
        assert len(data['errors']) > 0


class TestInboundExport:
    """入库记录导出"""

    def test_export_inbound(self, client, app):
        """导出入库记录为Excel"""
        c = client.post('/api/consumables', json={'code': 'HC001', 'name': '耗材'}).get_json()
        client.post('/api/stock/inbound', json={
            'consumable_id': c['id'], 'quantity': 100, 'batch_number': 'LOT001'
        })

        resp = client.get('/api/excel/export/inbound')
        assert resp.status_code == 200
        assert resp.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    def test_export_inbound_with_date_range(self, client, app):
        """按日期范围导出入库记录"""
        c = client.post('/api/consumables', json={'code': 'HC001', 'name': '耗材'}).get_json()
        client.post('/api/stock/inbound', json={
            'consumable_id': c['id'], 'quantity': 100, 'batch_number': 'LOT001'
        })

        from datetime import date
        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(f'/api/excel/export/inbound?start_date={today}&end_date={today}')
        assert resp.status_code == 200


class TestOutboundExport:
    """出库记录导出"""

    def test_export_outbound(self, client, app):
        """导出出库记录为Excel"""
        c = client.post('/api/consumables', json={'code': 'HC001', 'name': '耗材'}).get_json()
        client.post('/api/stock/inbound', json={
            'consumable_id': c['id'], 'quantity': 100, 'batch_number': 'LOT001'
        })
        client.post('/api/stock/outbound', json={
            'consumable_id': c['id'], 'quantity': 10, 'batch_number': 'LOT001'
        })

        resp = client.get('/api/excel/export/outbound')
        assert resp.status_code == 200
        assert resp.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class TestInventoryExport:
    """库存总览导出"""

    def test_export_inventory(self, client, app):
        """导出库存总览为Excel"""
        client.post('/api/consumables', json={'code': 'HC001', 'name': '耗材'})

        resp = client.get('/api/excel/export/inventory')
        assert resp.status_code == 200
        assert resp.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'