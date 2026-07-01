"""耗材基础信息模块测试 — CRUD 基本流程 + 类别管理 + 人员管理 + 科室管理"""
import pytest
from models import Consumable, Category, Staff, Department


class TestConsumableCRUD:
    """耗材 CRUD"""

    def test_create_consumable(self, client, app):
        """创建耗材"""
        resp = client.post('/api/consumables', json={
            'code': 'HC001',
            'name': '医用外科口罩',
            'brand': '测试品牌',
            'manufacturer': '测试厂家',
            'specification': '无菌型',
            'unit': '个',
            'category': '一次性耗材',
            'storage_location': 'A区1号架',
            'stock_warning_value': 100,
            'expiry_warning_days': 60,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['code'] == 'HC001'
        assert data['name'] == '医用外科口罩'
        assert data['category'] == '一次性耗材'
        assert data['stock_warning_value'] == 100

    def test_create_consumable_missing_required(self, client, app):
        """缺少必填字段返回400"""
        resp = client.post('/api/consumables', json={'code': 'HC001'})
        assert resp.status_code == 400

        resp = client.post('/api/consumables', json={'name': '测试'})
        assert resp.status_code == 400

    def test_create_consumable_duplicate_code(self, client, app):
        """重复编号返回400"""
        client.post('/api/consumables', json={'code': 'HC001', 'name': '耗材1'})
        resp = client.post('/api/consumables', json={'code': 'HC001', 'name': '耗材2'})
        assert resp.status_code == 400

    def test_list_consumables(self, client, app):
        """耗材列表"""
        client.post('/api/consumables', json={'code': 'HC001', 'name': '口罩'})
        client.post('/api/consumables', json={'code': 'HC002', 'name': '手套'})

        resp = client.get('/api/consumables')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 2

    def test_list_consumables_with_keyword(self, client, app):
        """关键词搜索耗材"""
        client.post('/api/consumables', json={'code': 'HC001', 'name': '医用外科口罩'})
        client.post('/api/consumables', json={'code': 'HC002', 'name': '乳胶手套'})

        resp = client.get('/api/consumables?keyword=口罩')
        data = resp.get_json()
        assert data['total'] >= 1
        assert any('口罩' in i['name'] for i in data['items'])

    def test_list_consumables_with_category(self, client, app):
        """按类别筛选耗材"""
        client.post('/api/consumables', json={
            'code': 'HC-CAT1', 'name': '类别耗材1', 'category': '试剂耗材'
        })
        client.post('/api/consumables', json={
            'code': 'HC-CAT2', 'name': '类别耗材2', 'category': '器械耗材'
        })

        resp = client.get('/api/consumables?category=试剂耗材')
        data = resp.get_json()
        for item in data['items']:
            if item['code'].startswith('HC-CAT'):
                assert item['category'] == '试剂耗材'

    def test_get_consumable_detail(self, client, app):
        """获取耗材详情"""
        r = client.post('/api/consumables', json={'code': 'HC001', 'name': '口罩'})
        cid = r.get_json()['id']

        resp = client.get(f'/api/consumables/{cid}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 'HC001'
        assert 'total_stock' in data  # include_stock=True

    def test_update_consumable(self, client, app):
        """更新耗材"""
        r = client.post('/api/consumables', json={'code': 'HC001', 'name': '口罩'})
        cid = r.get_json()['id']

        resp = client.put(f'/api/consumables/{cid}', json={
            'name': 'N95口罩',
            'brand': '3M',
            'stock_warning_value': 200,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == 'N95口罩'
        assert data['brand'] == '3M'
        assert data['stock_warning_value'] == 200

    def test_delete_consumable_with_zero_stock(self, client, app):
        """库存为0时可以删除耗材"""
        r = client.post('/api/consumables', json={'code': 'HC001', 'name': '口罩'})
        cid = r.get_json()['id']

        resp = client.delete(f'/api/consumables/{cid}')
        assert resp.status_code == 200

    def test_delete_consumable_with_stock_fails(self, client, app):
        """有库存时不能删除耗材"""
        r = client.post('/api/consumables', json={'code': 'HC001', 'name': '口罩'})
        cid = r.get_json()['id']

        # 入库后库存不为0
        client.post('/api/stock/inbound', json={
            'consumable_id': cid, 'quantity': 10, 'batch_number': 'LOT001'
        })

        resp = client.delete(f'/api/consumables/{cid}')
        assert resp.status_code == 400

    def test_list_all_consumables(self, client, app):
        """获取所有耗材（下拉选择用）"""
        client.post('/api/consumables', json={'code': 'HC001', 'name': '口罩'})
        client.post('/api/consumables', json={'code': 'HC002', 'name': '手套'})

        resp = client.get('/api/consumables/all')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2


class TestCategoryCRUD:
    """类别管理 CRUD"""

    def test_create_category(self, client, app):
        """创建类别"""
        resp = client.post('/api/categories', json={'name': '试剂类', 'sort_order': 1})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == '试剂类'
        assert data['sort_order'] == 1

    def test_create_category_duplicate_name(self, client, app):
        """重复类别名称返回400"""
        client.post('/api/categories', json={'name': '测试类别A'})
        resp = client.post('/api/categories', json={'name': '测试类别A'})
        assert resp.status_code == 400

    def test_list_categories(self, client, app):
        """类别列表"""
        client.post('/api/categories', json={'name': '类别X', 'sort_order': 0})
        resp = client.get('/api/categories')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_update_category(self, client, app):
        """更新类别"""
        r = client.post('/api/categories', json={'name': '旧类别'})
        cat_id = r.get_json()['id']

        resp = client.put(f'/api/categories/{cat_id}', json={'name': '新类别', 'sort_order': 5})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == '新类别'
        assert data['sort_order'] == 5

    def test_delete_category(self, client, app):
        """删除类别"""
        r = client.post('/api/categories', json={'name': '待删类别'})
        cat_id = r.get_json()['id']

        resp = client.delete(f'/api/categories/{cat_id}')
        assert resp.status_code == 200


class TestStaffCRUD:
    """人员管理 CRUD"""

    def test_create_staff(self, client, app):
        """创建人员"""
        # 先创建科室
        dept = client.post('/api/departments', json={'name': '检验科'}).get_json()

        resp = client.post('/api/staff', json={
            'name': '张三',
            'department_id': dept['id'],
            'role': '经办人',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == '张三'
        assert data['department_name'] == '检验科'
        assert data['role'] == '经办人'

    def test_create_staff_missing_name(self, client, app):
        """缺少姓名返回400"""
        resp = client.post('/api/staff', json={'role': '经办人'})
        assert resp.status_code == 400

    def test_list_staff(self, client, app):
        """人员列表"""
        client.post('/api/staff', json={'name': '张三'})
        client.post('/api/staff', json={'name': '李四'})

        resp = client.get('/api/staff')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 2

    def test_list_staff_by_department(self, client, app):
        """按科室筛选人员"""
        dept = client.post('/api/departments', json={'name': '检验科XX'}).get_json()
        client.post('/api/staff', json={'name': '王五', 'department_id': dept['id']})

        resp = client.get(f'/api/staff?department_id={dept["id"]}')
        data = resp.get_json()
        assert len(data) >= 1
        assert data[0]['department_id'] == dept['id']

    def test_update_staff(self, client, app):
        """更新人员"""
        r = client.post('/api/staff', json={'name': '赵六'})
        staff_id = r.get_json()['id']

        resp = client.put(f'/api/staff/{staff_id}', json={
            'name': '赵六六',
            'role': '经办人,领用人',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == '赵六六'
        assert data['role'] == '经办人,领用人'

    def test_delete_staff(self, client, app):
        """删除人员"""
        r = client.post('/api/staff', json={'name': '待删除'})
        staff_id = r.get_json()['id']

        resp = client.delete(f'/api/staff/{staff_id}')
        assert resp.status_code == 200


class TestDepartmentCRUD:
    """科室管理 CRUD"""

    def test_create_department(self, client, app):
        """创建科室"""
        resp = client.post('/api/departments', json={'name': '新科室', 'sort_order': 0})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == '新科室'

    def test_create_department_duplicate(self, client, app):
        """重复科室名称返回400"""
        client.post('/api/departments', json={'name': '唯一科室'})
        resp = client.post('/api/departments', json={'name': '唯一科室'})
        assert resp.status_code == 400

    def test_list_departments(self, client, app):
        """科室列表"""
        resp = client.get('/api/departments')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        # 默认科室
        assert len(data) >= 12

    def test_update_department(self, client, app):
        """更新科室"""
        r = client.post('/api/departments', json={'name': '测试科室A'})
        dept_id = r.get_json()['id']

        resp = client.put(f'/api/departments/{dept_id}', json={'name': '测试科室B', 'sort_order': 10})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == '测试科室B'
        assert data['sort_order'] == 10

    def test_delete_department(self, client, app):
        """删除科室"""
        r = client.post('/api/departments', json={'name': '待删科室'})
        dept_id = r.get_json()['id']

        resp = client.delete(f'/api/departments/{dept_id}')
        assert resp.status_code == 200