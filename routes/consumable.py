from flask import Blueprint, request, jsonify
from datetime import date as date_type
from models import db, Consumable, StockBatch, InboundRecord, OutboundRecord
from utils.db import ilike_filter as _ilike_filter


def _to_date(val):
    """将字符串或 None 转为 Python date 对象，用于 SQLAlchemy Date 字段赋值"""
    if isinstance(val, str) and val:
        return date_type.fromisoformat(val)
    if isinstance(val, date_type):
        return val
    return None

consumable_bp = Blueprint('consumable', __name__)


@consumable_bp.route('', methods=['GET'])
def list_consumables():
    """耗材列表（分页 + 搜索 + 类别筛选）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    category = request.args.get('category', '').strip()
    include_stock = request.args.get('include_stock', 'false').lower() == 'true'

    query = Consumable.query
    if keyword:
        query = query.filter(
            db.or_(
                _ilike_filter(Consumable.code, keyword),
                _ilike_filter(Consumable.name, keyword),
                _ilike_filter(Consumable.brand, keyword),
                _ilike_filter(Consumable.manufacturer, keyword),
                _ilike_filter(Consumable.specification, keyword),
            )
        )
    if category:
        query = query.filter(Consumable.category == category)
    query = query.order_by(Consumable.code)
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [c.to_dict(include_stock=include_stock) for c in pagination.items]
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.per_page,
        'pages': pagination.pages,
    })


@consumable_bp.route('/<int:consumable_id>', methods=['GET'])
def get_consumable(consumable_id):
    """获取单条耗材详情"""
    c = Consumable.query.get_or_404(consumable_id)
    return jsonify(c.to_dict(include_stock=True))


@consumable_bp.route('', methods=['POST'])
def create_consumable():
    """新增耗材"""
    data = request.get_json()
    if not data or not data.get('code') or not data.get('name'):
        return jsonify({'error': '耗材编号和名称为必填项'}), 400

    if Consumable.query.filter_by(code=data['code']).first():
        return jsonify({'error': f'耗材编号 {data["code"]} 已存在'}), 400

    initial_stock = data.get('initial_stock', 0) or 0
    c = Consumable(
        code=data['code'],
        name=data['name'],
        brand=data.get('brand'),
        manufacturer=data.get('manufacturer'),
        specification=data.get('specification'),
        unit=data.get('unit'),
        category=data.get('category'),
        storage_location=data.get('storage_location'),
        initial_stock=initial_stock,
        stock_warning_value=data.get('stock_warning_value', 0),
        expiry_warning_days=data.get('expiry_warning_days', 0),
        remark=data.get('remark'),
    )
    db.session.add(c)
    db.session.flush()  # 先 flush 以获取 c.id
    # 期初库存同步创建初始批次，使 total_stock 计算正确
    if initial_stock > 0:
        batch = StockBatch(
            consumable_id=c.id,
            batch_number='期初库存',
            quantity=initial_stock,
            production_date=_to_date(data.get('initial_production_date')),
            expiry_date=_to_date(data.get('initial_expiry_date')),
            storage_location=data.get('storage_location'),
            remark='系统自动创建（期初库存）',
        )
        db.session.add(batch)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@consumable_bp.route('/<int:consumable_id>', methods=['PUT'])
def update_consumable(consumable_id):
    """更新耗材"""
    c = Consumable.query.get_or_404(consumable_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': '请提供更新数据'}), 400

    # 如果修改编号，检查唯一性
    if 'code' in data and data['code'] != c.code:
        if Consumable.query.filter_by(code=data['code']).first():
            return jsonify({'error': f'耗材编号 {data["code"]} 已存在'}), 400
        c.code = data['code']

    for field in ['name', 'brand', 'manufacturer', 'specification', 'unit',
                  'category', 'storage_location',
                  'stock_warning_value', 'expiry_warning_days', 'remark']:
        if field in data:
            setattr(c, field, data[field])

    # 单独处理 initial_stock：同步调整期初库存批次
    if 'initial_stock' in data:
        new_initial = data['initial_stock'] or 0
        old_initial = c.initial_stock or 0
        diff = new_initial - old_initial
        c.initial_stock = new_initial
        if diff != 0:
            # 查找期初库存批次
            init_batch = StockBatch.query.filter_by(
                consumable_id=c.id, batch_number='期初库存'
            ).first()
            if init_batch:
                init_batch.quantity += diff
                if init_batch.quantity <= 0:
                    db.session.delete(init_batch)
            elif diff > 0:
                # 之前没有期初批次，新建
                batch = StockBatch(
                    consumable_id=c.id,
                    batch_number='期初库存',
                    quantity=diff,
                    production_date=_to_date(data.get('initial_production_date')),
                    expiry_date=_to_date(data.get('initial_expiry_date')),
                    remark='系统自动创建（期初库存）',
                )
                db.session.add(batch)

    # 同步更新期初库存批次的生产日期和失效日期
    if 'initial_production_date' in data or 'initial_expiry_date' in data:
        init_batch = StockBatch.query.filter_by(
            consumable_id=c.id, batch_number='期初库存'
        ).first()
        if init_batch:
            if 'initial_production_date' in data:
                init_batch.production_date = _to_date(data['initial_production_date'])
            if 'initial_expiry_date' in data:
                init_batch.expiry_date = _to_date(data['initial_expiry_date'])

    db.session.commit()
    return jsonify(c.to_dict())


@consumable_bp.route('/<int:consumable_id>', methods=['DELETE'])
def delete_consumable(consumable_id):
    """删除耗材（有历史记录时拒绝删除）"""
    c = Consumable.query.get_or_404(consumable_id)
    # 检查是否有库存
    if c.total_stock > 0:
        return jsonify({'error': '该耗材仍有库存，无法删除。请先出库清零后再删除。'}), 400
    # 检查是否有入库/出库历史记录
    inbound_count = InboundRecord.query.filter_by(consumable_id=consumable_id).count()
    if inbound_count > 0:
        return jsonify({'error': f'该耗材存在 {inbound_count} 条入库记录，无法删除。历史记录需保留以供追溯。'}), 400
    outbound_count = OutboundRecord.query.filter_by(consumable_id=consumable_id).count()
    if outbound_count > 0:
        return jsonify({'error': f'该耗材存在 {outbound_count} 条出库记录，无法删除。历史记录需保留以供追溯。'}), 400
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': '删除成功'})


@consumable_bp.route('/all', methods=['GET'])
def list_all_consumables():
    """获取所有耗材（下拉选择用，不分页）"""
    items = Consumable.query.order_by(Consumable.code).all()
    return jsonify([c.to_dict() for c in items])