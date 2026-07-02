import json
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Category(db.Model):
    """耗材类别"""
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False, comment='类别名称')
    sort_order = db.Column(db.Integer, default=0, comment='排序序号')
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'sort_order': self.sort_order,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class Staff(db.Model):
    """人员管理"""
    __tablename__ = 'staff'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='姓名')
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True, comment='所属科室ID')
    role = db.Column(db.String(200), nullable=True, comment='角色（经办人/领用人/责任人，逗号分隔）')
    sort_order = db.Column(db.Integer, default=0, comment='排序序号')
    created_at = db.Column(db.DateTime, default=datetime.now)

    department = db.relationship('Department', backref='staffs')

    def to_dict(self):
        data = {
            'id': self.id,
            'name': self.name,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'role': self.role,
            'sort_order': self.sort_order,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }
        return data


class Consumable(db.Model):
    """耗材基础信息"""
    __tablename__ = 'consumable'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(50), unique=True, nullable=False, comment='耗材编号')
    name = db.Column(db.String(200), nullable=False, comment='耗材名称')
    brand = db.Column(db.String(200), nullable=True, comment='品牌名称')
    manufacturer = db.Column(db.String(200), nullable=True, comment='生产厂家')
    specification = db.Column(db.String(200), nullable=True, comment='规格型号')
    unit = db.Column(db.String(50), nullable=True, comment='单位')
    category = db.Column(db.String(100), nullable=True, comment='耗材类别')
    storage_location = db.Column(db.String(200), nullable=True, comment='存放位置')
    initial_stock = db.Column(db.Integer, default=0, comment='期初数量')
    stock_warning_value = db.Column(db.Integer, default=0, comment='库存预警值')
    expiry_warning_days = db.Column(db.Integer, default=0, comment='近效期预警天数')
    remark = db.Column(db.Text, nullable=True, comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    stock_batches = db.relationship('StockBatch', backref='consumable', lazy='dynamic',
                                    cascade='all, delete-orphan')
    inbound_records = db.relationship('InboundRecord', backref='consumable', lazy='dynamic',
                                      cascade='all, delete-orphan')
    outbound_records = db.relationship('OutboundRecord', backref='consumable', lazy='dynamic',
                                       cascade='all, delete-orphan')

    @property
    def total_stock(self):
        """当前库存总量（所有批次之和）"""
        result = db.session.query(db.func.coalesce(db.func.sum(StockBatch.quantity), 0)) \
            .filter(StockBatch.consumable_id == self.id) \
            .scalar()
        return int(result)

    @property
    def total_inbound(self):
        """累计入库量"""
        result = db.session.query(db.func.coalesce(db.func.sum(InboundRecord.quantity), 0)) \
            .filter(InboundRecord.consumable_id == self.id) \
            .scalar()
        return int(result)

    @property
    def total_outbound(self):
        """累计出库量"""
        result = db.session.query(db.func.coalesce(db.func.sum(OutboundRecord.quantity), 0)) \
            .filter(OutboundRecord.consumable_id == self.id) \
            .scalar()
        return int(result)

    @property
    def stock_status(self):
        """库存状态: 正常/预警/不足
        三级判定：不足(≤0或≤预警值且>0) / 预警(≤预警值×1.5且>预警值) / 正常(>预警值×1.5)
        """
        total = self.total_stock
        if total <= 0:
            return '库存不足'
        elif self.stock_warning_value > 0 and total <= self.stock_warning_value:
            return '库存不足'
        elif self.stock_warning_value > 0 and total <= self.stock_warning_value * 1.5:
            return '库存预警'
        else:
            return '库存正常'

    @property
    def expiry_status(self):
        """效期状态: 正常/近效期/已过期"""
        today = date.today()
        nearest_expiry = db.session.query(db.func.min(StockBatch.expiry_date)) \
            .filter(StockBatch.consumable_id == self.id,
                    StockBatch.quantity > 0,
                    StockBatch.expiry_date.isnot(None)) \
            .scalar()
        if nearest_expiry is None:
            return '效期正常'
        if nearest_expiry < today:
            return '已过期'
        days_left = (nearest_expiry - today).days
        if self.expiry_warning_days > 0 and days_left <= self.expiry_warning_days:
            return '近效期'
        return '效期正常'

    def to_dict(self, include_stock=False):
        data = {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'brand': self.brand,
            'manufacturer': self.manufacturer,
            'specification': self.specification,
            'unit': self.unit,
            'category': self.category,
            'storage_location': self.storage_location,
            'initial_stock': self.initial_stock,
            'stock_warning_value': self.stock_warning_value,
            'expiry_warning_days': self.expiry_warning_days,
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
        # 附带期初库存批次的生产日期和失效日期，用于编辑表单回显
        init_batch = StockBatch.query.filter_by(
            consumable_id=self.id, batch_number='期初库存'
        ).first()
        if init_batch:
            data['initial_production_date'] = init_batch.production_date.strftime('%Y-%m-%d') if init_batch.production_date else None
            data['initial_expiry_date'] = init_batch.expiry_date.strftime('%Y-%m-%d') if init_batch.expiry_date else None
        else:
            data['initial_production_date'] = None
            data['initial_expiry_date'] = None
        if include_stock:
            data.update({
                'total_inbound': self.total_inbound,
                'total_outbound': self.total_outbound,
                'total_stock': self.total_stock,
                'stock_status': self.stock_status,
                'expiry_status': self.expiry_status,
            })
        return data


class Department(db.Model):
    """科室配置"""
    __tablename__ = 'department'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), unique=True, nullable=False, comment='科室名称')
    sort_order = db.Column(db.Integer, default=0, comment='排序序号')
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'sort_order': self.sort_order,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class StockBatch(db.Model):
    """库存批次"""
    __tablename__ = 'stock_batch'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    consumable_id = db.Column(db.Integer, db.ForeignKey('consumable.id'), nullable=False, comment='耗材ID')
    batch_number = db.Column(db.String(100), nullable=True, comment='批号')
    production_date = db.Column(db.Date, nullable=True, comment='生产日期')
    expiry_date = db.Column(db.Date, nullable=True, comment='失效日期')
    quantity = db.Column(db.Integer, default=0, comment='当前库存数量')
    storage_location = db.Column(db.String(200), nullable=True, comment='存放位置')
    remark = db.Column(db.Text, nullable=True, comment='备注')
    inbound_record_id = db.Column(db.Integer, db.ForeignKey('inbound_record.id'), nullable=True, comment='关联入库记录ID')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self, include_consumable=False):
        data = {
            'id': self.id,
            'consumable_id': self.consumable_id,
            'batch_number': self.batch_number,
            'production_date': self.production_date.strftime('%Y-%m-%d') if self.production_date else None,
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else None,
            'quantity': self.quantity,
            'storage_location': self.storage_location,
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }
        if include_consumable and self.consumable:
            data['consumable_name'] = self.consumable.name
            data['consumable_code'] = self.consumable.code
            data['consumable_spec'] = self.consumable.specification
            data['consumable_unit'] = self.consumable.unit
        return data

    @property
    def expiry_status(self):
        """批次效期状态: 正常/近效期/已过期"""
        if self.expiry_date is None:
            return '效期正常'
        today = date.today()
        if self.expiry_date < today:
            return '已过期'
        if self.consumable and self.consumable.expiry_warning_days > 0:
            days_left = (self.expiry_date - today).days
            if days_left <= self.consumable.expiry_warning_days:
                return '近效期'
        return '效期正常'


class InboundRecord(db.Model):
    """入库记录"""
    __tablename__ = 'inbound_record'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    consumable_id = db.Column(db.Integer, db.ForeignKey('consumable.id'), nullable=False, comment='耗材ID')
    document_number = db.Column(db.String(50), nullable=True, comment='入库单号')
    batch_number = db.Column(db.String(100), nullable=True, comment='批号')
    production_date = db.Column(db.Date, nullable=True, comment='生产日期')
    expiry_date = db.Column(db.Date, nullable=True, comment='失效日期')
    quantity = db.Column(db.Integer, nullable=False, comment='入库数量')
    operator = db.Column(db.String(100), nullable=True, comment='经办人')
    storage_location = db.Column(db.String(200), nullable=True, comment='存放位置')
    inbound_time = db.Column(db.DateTime, default=datetime.now, comment='入库时间')
    remark = db.Column(db.Text, nullable=True, comment='备注')

    def to_dict(self, include_consumable=False):
        data = {
            'id': self.id,
            'consumable_id': self.consumable_id,
            'document_number': self.document_number,
            'batch_number': self.batch_number,
            'production_date': self.production_date.strftime('%Y-%m-%d') if self.production_date else None,
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else None,
            'quantity': self.quantity,
            'operator': self.operator,
            'storage_location': self.storage_location,
            'inbound_time': self.inbound_time.strftime('%Y-%m-%d %H:%M:%S') if self.inbound_time else None,
            'remark': self.remark,
        }
        if include_consumable and self.consumable:
            data['consumable_name'] = self.consumable.name
            data['consumable_code'] = self.consumable.code
            data['consumable_spec'] = self.consumable.specification
            data['consumable_unit'] = self.consumable.unit
        return data


class OutboundRecord(db.Model):
    """出库记录"""
    __tablename__ = 'outbound_record'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    consumable_id = db.Column(db.Integer, db.ForeignKey('consumable.id'), nullable=False, comment='耗材ID')
    document_number = db.Column(db.String(50), nullable=True, comment='出库单号')
    batch_number = db.Column(db.String(100), nullable=True, comment='批号')
    batch_detail = db.Column(db.Text, nullable=True, comment='扣减明细JSON，如[{"batch_number":"HC00120260701001","quantity":2}]')
    quantity = db.Column(db.Integer, nullable=False, comment='出库数量')
    recipient = db.Column(db.String(100), nullable=True, comment='领用人')
    department = db.Column(db.String(200), nullable=True, comment='领用科室')
    operator = db.Column(db.String(100), nullable=True, comment='经办人')
    outbound_time = db.Column(db.DateTime, default=datetime.now, comment='出库时间')
    remark = db.Column(db.Text, nullable=True, comment='备注')

    def to_dict(self, include_consumable=False):
        data = {
            'id': self.id,
            'consumable_id': self.consumable_id,
            'document_number': self.document_number,
            'batch_number': self.batch_number,
            'batch_detail': json.loads(self.batch_detail) if self.batch_detail else None,
            'quantity': self.quantity,
            'recipient': self.recipient,
            'department': self.department,
            'operator': self.operator,
            'outbound_time': self.outbound_time.strftime('%Y-%m-%d %H:%M:%S') if self.outbound_time else None,
            'remark': self.remark,
        }
        if include_consumable and self.consumable:
            data['consumable_name'] = self.consumable.name
            data['consumable_code'] = self.consumable.code
            data['consumable_spec'] = self.consumable.specification
            data['consumable_unit'] = self.consumable.unit
        return data


class InventoryCheck(db.Model):
    """盘点主表"""
    __tablename__ = 'inventory_check'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    check_date = db.Column(db.Date, nullable=False, comment='盘点日期')
    status = db.Column(db.String(20), default='draft', comment='状态：draft/confirmed')
    remark = db.Column(db.Text, nullable=True, comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now)

    items = db.relationship('InventoryCheckItem', backref='check', lazy='dynamic',
                            cascade='all, delete-orphan')

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'check_date': self.check_date.strftime('%Y-%m-%d') if self.check_date else None,
            'status': self.status,
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }
        if include_items:
            data['items'] = [item.to_dict() for item in self.items.all()]
        else:
            data['item_count'] = self.items.count()
        return data


class InventoryCheckItem(db.Model):
    """盘点明细"""
    __tablename__ = 'inventory_check_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    check_id = db.Column(db.Integer, db.ForeignKey('inventory_check.id'), nullable=False, comment='盘点ID')
    consumable_id = db.Column(db.Integer, db.ForeignKey('consumable.id'), nullable=False, comment='耗材ID')
    system_quantity = db.Column(db.Integer, default=0, comment='系统库存数量')
    actual_quantity = db.Column(db.Integer, default=None, comment='实盘数量')
    difference = db.Column(db.Integer, default=0, comment='盈亏数量')
    remark = db.Column(db.Text, nullable=True, comment='备注')

    consumable = db.relationship('Consumable')

    def to_dict(self):
        data = {
            'id': self.id,
            'check_id': self.check_id,
            'consumable_id': self.consumable_id,
            'system_quantity': self.system_quantity,
            'actual_quantity': self.actual_quantity,
            'difference': self.difference,
            'remark': self.remark,
        }
        if self.consumable:
            data['consumable_code'] = self.consumable.code
            data['consumable_name'] = self.consumable.name
            data['consumable_spec'] = self.consumable.specification
            data['consumable_unit'] = self.consumable.unit
            data['category'] = self.consumable.category
        return data