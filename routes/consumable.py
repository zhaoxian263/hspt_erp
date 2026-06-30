from flask import Blueprint, request, jsonify
from models import db, Consumable

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
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
                Consumable.brand.contains(keyword),
                Consumable.manufacturer.contains(keyword),
                Consumable.specification.contains(keyword),
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

    c = Consumable(
        code=data['code'],
        name=data['name'],
        brand=data.get('brand'),
        manufacturer=data.get('manufacturer'),
        specification=data.get('specification'),
        unit=data.get('unit'),
        category=data.get('category'),
        storage_location=data.get('storage_location'),
        initial_stock=data.get('initial_stock', 0),
        stock_warning_value=data.get('stock_warning_value', 0),
        expiry_warning_days=data.get('expiry_warning_days', 0),
        remark=data.get('remark'),
    )
    db.session.add(c)
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
                  'category', 'storage_location', 'initial_stock',
                  'stock_warning_value', 'expiry_warning_days', 'remark']:
        if field in data:
            setattr(c, field, data[field])

    db.session.commit()
    return jsonify(c.to_dict())


@consumable_bp.route('/<int:consumable_id>', methods=['DELETE'])
def delete_consumable(consumable_id):
    """删除耗材（连同出入库记录和批次）"""
    c = Consumable.query.get_or_404(consumable_id)
    # 检查是否有库存
    if c.total_stock > 0:
        return jsonify({'error': '该耗材仍有库存，无法删除。请先出库清零后再删除。'}), 400

    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': '删除成功'})


@consumable_bp.route('/all', methods=['GET'])
def list_all_consumables():
    """获取所有耗材（下拉选择用，不分页）"""
    items = Consumable.query.order_by(Consumable.code).all()
    return jsonify([c.to_dict() for c in items])