from datetime import datetime, date
from flask import Blueprint, request, jsonify
from models import db, Consumable, StockBatch, InboundRecord, OutboundRecord, InventoryCheck

stock_bp = Blueprint('stock', __name__)


def _generate_document_number(prefix):
    """生成单号：RK+日期+序号 或 CK+日期+序号"""
    today_str = datetime.now().strftime('%Y%m%d')
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    if prefix == 'RK':
        model = InboundRecord
        field = InboundRecord.inbound_time
    else:
        model = OutboundRecord
        field = OutboundRecord.outbound_time

    # 查找今天已有的最大序号
    last_record = model.query.filter(
        field >= today_start,
        field <= today_end,
    ).order_by(model.id.desc()).first()

    seq = 1
    if last_record and last_record.document_number:
        try:
            parts = last_record.document_number.split('-')
            if len(parts) == 2:
                seq = int(parts[1]) + 1
        except (ValueError, IndexError):
            seq = 1

    return f'{prefix}{today_str}-{seq:03d}'


# ======================== 入库管理 ========================

@stock_bp.route('/inbound', methods=['GET'])
def list_inbound():
    """入库记录列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = InboundRecord.query
    if keyword:
        query = query.join(Consumable).filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
                InboundRecord.batch_number.contains(keyword),
                InboundRecord.operator.contains(keyword),
                InboundRecord.document_number.contains(keyword),
            )
        )
    if start_date:
        query = query.filter(InboundRecord.inbound_time >= start_date)
    if end_date:
        query = query.filter(InboundRecord.inbound_time <= end_date + ' 23:59:59')

    query = query.order_by(InboundRecord.inbound_time.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [r.to_dict(include_consumable=True) for r in pagination.items]
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.per_page,
        'pages': pagination.pages,
    })


@stock_bp.route('/inbound', methods=['POST'])
def create_inbound():
    """新增入库记录（同时更新库存批次，自动生成单号）"""
    data = request.get_json()
    if not data or not data.get('consumable_id') or not data.get('quantity'):
        return jsonify({'error': '耗材和数量为必填项'}), 400

    consumable_id = data['consumable_id']
    quantity = int(data['quantity'])
    batch_number = data.get('batch_number', '')

    # 验证耗材存在
    consumable = Consumable.query.get(consumable_id)
    if not consumable:
        return jsonify({'error': '耗材不存在'}), 404

    # 解析日期
    production_date = _parse_date(data.get('production_date'))
    expiry_date = _parse_date(data.get('expiry_date'))
    inbound_time = _parse_datetime(data.get('inbound_time'))

    # 自动生成入库单号
    document_number = _generate_document_number('RK')

    # 创建入库记录
    record = InboundRecord(
        consumable_id=consumable_id,
        document_number=document_number,
        batch_number=batch_number,
        production_date=production_date,
        expiry_date=expiry_date,
        quantity=quantity,
        operator=data.get('operator'),
        storage_location=data.get('storage_location'),
        inbound_time=inbound_time,
        remark=data.get('remark'),
    )
    db.session.add(record)

    # 每次入库都创建独立批次（保证 FIFO 顺序正确）
    batch = StockBatch(
        consumable_id=consumable_id,
        batch_number=batch_number,
        production_date=production_date,
        expiry_date=expiry_date,
        quantity=quantity,
        storage_location=data.get('storage_location'),
        remark=data.get('remark'),
    )
    db.session.add(batch)

    db.session.commit()
    return jsonify(record.to_dict(include_consumable=True)), 201


@stock_bp.route('/inbound/<int:record_id>', methods=['DELETE'])
def delete_inbound(record_id):
    """删除入库记录（同时扣减库存批次）"""
    record = InboundRecord.query.get_or_404(record_id)
    # 扣减对应批次库存
    batch = StockBatch.query.filter_by(
        consumable_id=record.consumable_id,
        batch_number=record.batch_number,
    ).first()
    if batch:
        batch.quantity -= record.quantity
        if batch.quantity <= 0:
            db.session.delete(batch)
    db.session.delete(record)
    db.session.commit()
    return jsonify({'message': '删除成功'})


@stock_bp.route('/inbound/<int:record_id>/print', methods=['GET'])
def print_inbound(record_id):
    """获取入库单打印数据"""
    record = InboundRecord.query.get_or_404(record_id)
    data = record.to_dict(include_consumable=True)
    # 打印数据额外包含耗材详细信息
    if record.consumable:
        data['consumable_brand'] = record.consumable.brand
        data['consumable_manufacturer'] = record.consumable.manufacturer
        data['consumable_spec'] = record.consumable.specification
        data['consumable_unit'] = record.consumable.unit
    return jsonify(data)


# ======================== 出库管理 ========================

@stock_bp.route('/outbound', methods=['GET'])
def list_outbound():
    """出库记录列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    document_number = request.args.get('document_number', '').strip()

    query = OutboundRecord.query
    if document_number:
        query = query.filter(OutboundRecord.document_number == document_number)
    if keyword:
        query = query.join(Consumable).filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
                OutboundRecord.batch_number.contains(keyword),
                OutboundRecord.recipient.contains(keyword),
                OutboundRecord.department.contains(keyword),
                OutboundRecord.document_number.contains(keyword),
            )
        )
    if start_date:
        query = query.filter(OutboundRecord.outbound_time >= start_date)
    if end_date:
        query = query.filter(OutboundRecord.outbound_time <= end_date + ' 23:59:59')

    query = query.order_by(OutboundRecord.outbound_time.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [r.to_dict(include_consumable=True) for r in pagination.items]
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.per_page,
        'pages': pagination.pages,
    })


@stock_bp.route('/outbound', methods=['POST'])
def create_outbound():
    """新增出库记录（支持单条或多条，自动生成单号）"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400

    # 支持批量出库：检查是否是数组格式
    items = data.get('items', [])
    if items:
        # 批量模式：items 是数组，每个元素包含 consumable_id 和 quantity
        if not isinstance(items, list):
            return jsonify({'error': 'items 必须是数组'}), 400
        # 公共字段（从 data 中提取）
        recipient = data.get('recipient', '')
        department = data.get('department', '')
        operator = data.get('operator', '')
        outbound_time = _parse_datetime(data.get('outbound_time'))
        remark = data.get('remark', '')
        # 自动生成一个出库单号供本次所有明细共用
        document_number = _generate_document_number('CK')

        created_records = []
        for item in items:
            consumable_id = item.get('consumable_id')
            quantity = int(item.get('quantity', 0))
            if not consumable_id or quantity <= 0:
                continue

            consumable = Consumable.query.get(consumable_id)
            if not consumable:
                return jsonify({'error': f'耗材ID {consumable_id} 不存在'}), 404
            if consumable.total_stock < quantity:
                return jsonify({'error': f'耗材 {consumable.name} 库存不足，当前 {consumable.total_stock}，申请 {quantity}'}), 400

            batch_number = item.get('batch_number', '')

            # 扣减库存批次（先进先出）
            if batch_number:
                target_batch = StockBatch.query.filter_by(consumable_id=consumable_id, batch_number=batch_number).first()
                if target_batch and target_batch.quantity >= quantity:
                    batches = [target_batch]
                else:
                    # 指定批号找不到或库存不足，回退到FIFO
                    batches = StockBatch.query.filter(
                        StockBatch.consumable_id == consumable_id,
                        StockBatch.quantity > 0,
                    ).order_by(StockBatch.expiry_date.asc().nullslast(), StockBatch.created_at.asc()).all()
            else:
                batches = StockBatch.query.filter(
                    StockBatch.consumable_id == consumable_id,
                    StockBatch.quantity > 0,
                ).order_by(StockBatch.expiry_date.asc().nullslast(), StockBatch.created_at.asc()).all()

            # 创建出库记录
            record = OutboundRecord(
                consumable_id=consumable_id,
                document_number=document_number,
                batch_number=batch_number,
                quantity=quantity,
                recipient=recipient,
                department=department,
                operator=operator,
                outbound_time=outbound_time,
                remark=remark,
            )
            db.session.add(record)

            # 扣减批次库存
            remaining = quantity
            for batch in batches:
                if remaining <= 0:
                    break
                if batch.quantity <= remaining:
                    remaining -= batch.quantity
                    batch.quantity = 0
                else:
                    batch.quantity -= remaining
                    remaining = 0

            # 删除库存为0的批次
            for batch in StockBatch.query.filter(StockBatch.quantity <= 0).all():
                db.session.delete(batch)

            # 更新批号记录
            if not batch_number and batches:
                used_batches = [b.batch_number or '' for b in batches if b.quantity >= 0]
                record.batch_number = ', '.join(filter(None, used_batches))[:100]

            created_records.append(record)

        db.session.commit()
        return jsonify({'document_number': document_number, 'count': len(created_records)}), 201
    else:
        # 单条模式（兼容旧版）
        if not data.get('consumable_id') or not data.get('quantity'):
            return jsonify({'error': '耗材和数量为必填项'}), 400

        consumable_id = data['consumable_id']
        quantity = int(data['quantity'])

        consumable = Consumable.query.get(consumable_id)
        if not consumable:
            return jsonify({'error': '耗材不存在'}), 404

        if consumable.total_stock < quantity:
            return jsonify({'error': f'库存不足，当前库存 {consumable.total_stock}，申请出库 {quantity}'}), 400

        batch_number = data.get('batch_number', '')
        outbound_time = _parse_datetime(data.get('outbound_time'))
        document_number = _generate_document_number('CK')

        if batch_number:
            target_batch = StockBatch.query.filter_by(consumable_id=consumable_id, batch_number=batch_number).first()
            if target_batch and target_batch.quantity >= quantity:
                batches = [target_batch]
            else:
                # 指定批号找不到或库存不足，回退到FIFO
                batches = StockBatch.query.filter(
                    StockBatch.consumable_id == consumable_id,
                    StockBatch.quantity > 0,
                ).order_by(StockBatch.expiry_date.asc().nullslast(), StockBatch.created_at.asc()).all()
        else:
            batches = StockBatch.query.filter(
                StockBatch.consumable_id == consumable_id,
                StockBatch.quantity > 0,
            ).order_by(StockBatch.expiry_date.asc().nullslast(), StockBatch.created_at.asc()).all()

        record = OutboundRecord(
            consumable_id=consumable_id,
            document_number=document_number,
            batch_number=batch_number,
            quantity=quantity,
            recipient=data.get('recipient'),
            department=data.get('department'),
            operator=data.get('operator'),
            outbound_time=outbound_time,
            remark=data.get('remark'),
        )
        db.session.add(record)

        remaining = quantity
        for batch in batches:
            if remaining <= 0:
                break
            if batch.quantity <= remaining:
                remaining -= batch.quantity
                batch.quantity = 0
            else:
                batch.quantity -= remaining
                remaining = 0

        for batch in StockBatch.query.filter(StockBatch.quantity <= 0).all():
            db.session.delete(batch)

        if not batch_number and batches:
            used_batches = [b.batch_number or '' for b in batches if b.quantity >= 0]
            record.batch_number = ', '.join(filter(None, used_batches))[:100]

        db.session.commit()
        return jsonify(record.to_dict(include_consumable=True)), 201


@stock_bp.route('/outbound/<int:record_id>', methods=['DELETE'])
def delete_outbound(record_id):
    """删除出库记录（同时恢复库存批次）"""
    record = OutboundRecord.query.get_or_404(record_id)
    # 恢复批次库存：查找同批号批次，有则加回，无则新建
    for bn in (record.batch_number or '').split(','):
        bn = bn.strip()
        if not bn:
            continue
        batch = StockBatch.query.filter_by(
            consumable_id=record.consumable_id,
            batch_number=bn,
        ).first()
        if batch:
            batch.quantity += record.quantity
        else:
            batch = StockBatch(
                consumable_id=record.consumable_id,
                batch_number=bn,
                quantity=record.quantity,
            )
            db.session.add(batch)
        break  # 只处理第一个批号

    db.session.delete(record)
    db.session.commit()
    return jsonify({'message': '删除成功'})


@stock_bp.route('/outbound/<int:record_id>/print', methods=['GET'])
def print_outbound(record_id):
    """获取出库单打印数据"""
    record = OutboundRecord.query.get_or_404(record_id)
    data = record.to_dict(include_consumable=True)
    if record.consumable:
        data['consumable_brand'] = record.consumable.brand
        data['consumable_manufacturer'] = record.consumable.manufacturer
        data['consumable_spec'] = record.consumable.specification
        data['consumable_unit'] = record.consumable.unit
    return jsonify(data)


# ======================== 库存查询与预警 ========================

@stock_bp.route('/inventory', methods=['GET'])
def list_inventory():
    """库存总览（含预警状态）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)
    keyword = request.args.get('keyword', '').strip()
    status_filter = request.args.get('status', '').strip()  # all/normal/low_or_warning/expiry_warning/expired
    category = request.args.get('category', '').strip()

    query = Consumable.query
    if keyword:
        query = query.filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
                Consumable.brand.contains(keyword),
                Consumable.manufacturer.contains(keyword),
            )
        )
    if category:
        query = query.filter(Consumable.category == category)

    items = query.order_by(Consumable.code).all()
    result = []
    for c in items:
        item = c.to_dict(include_stock=True)
        item['stock_batches'] = [b.to_dict() for b in c.stock_batches.filter(StockBatch.quantity > 0).all()]
        # 状态过滤
        if status_filter == 'normal' and item['stock_status'] != '库存正常':
            continue
        elif status_filter == 'low_or_warning' and item['stock_status'] not in ('库存不足', '库存预警'):
            continue
        elif status_filter == 'expiry_warning' and item['expiry_status'] != '近效期':
            continue
        elif status_filter == 'expired' and item['expiry_status'] != '已过期':
            continue
        result.append(item)

    # 分页
    total = len(result)
    start = (page - 1) * page_size
    end = start + page_size
    paged = result[start:end]

    return jsonify({
        'items': paged,
        'total': total,
        'page': page,
        'page_size': page_size,
    })


@stock_bp.route('/batches', methods=['GET'])
def list_batches():
    """库存批次明细"""
    consumable_id = request.args.get('consumable_id', type=int)
    query = StockBatch.query.filter(StockBatch.quantity > 0)
    if consumable_id:
        query = query.filter_by(consumable_id=consumable_id)
    query = query.order_by(StockBatch.expiry_date.asc().nullslast())
    items = [b.to_dict(include_consumable=True) for b in query.all()]
    return jsonify({'items': items, 'total': len(items)})


@stock_bp.route('/period-inventory', methods=['GET'])
def period_inventory():
    """期间库存查询（期初+入库-出库=期末）"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    keyword = request.args.get('keyword', '').strip()
    category = request.args.get('category', '').strip()

    if not start_date or not end_date:
        return jsonify({'error': '请提供开始日期和结束日期'}), 400

    query = Consumable.query
    if keyword:
        query = query.filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
            )
        )
    if category:
        query = query.filter(Consumable.category == category)

    consumables = query.order_by(Consumable.code).all()
    result = []
    for c in consumables:
        # 期初 = initial_stock
        initial = c.initial_stock or 0
        # 期间入库
        inbound_qty = db.session.query(db.func.coalesce(db.func.sum(InboundRecord.quantity), 0)) \
            .filter(InboundRecord.consumable_id == c.id,
                    InboundRecord.inbound_time >= start_date,
                    InboundRecord.inbound_time <= end_date + ' 23:59:59') \
            .scalar() or 0
        # 期间出库
        outbound_qty = db.session.query(db.func.coalesce(db.func.sum(OutboundRecord.quantity), 0)) \
            .filter(OutboundRecord.consumable_id == c.id,
                    OutboundRecord.outbound_time >= start_date,
                    OutboundRecord.outbound_time <= end_date + ' 23:59:59') \
            .scalar() or 0
        # 期末
        ending = initial + int(inbound_qty) - int(outbound_qty)

        result.append({
            'id': c.id,
            'code': c.code,
            'name': c.name,
            'specification': c.specification,
            'unit': c.unit,
            'category': c.category,
            'initial_stock': initial,
            'period_inbound': int(inbound_qty),
            'period_outbound': int(outbound_qty),
            'ending_stock': ending,
            'current_stock': c.total_stock,
        })

    return jsonify({'items': result, 'total': len(result)})


@stock_bp.route('/dashboard', methods=['GET'])
def dashboard():
    """首页仪表盘数据"""
    total_consumables = Consumable.query.count()
    total_inbound = db.session.query(db.func.sum(InboundRecord.quantity)).scalar() or 0
    total_outbound = db.session.query(db.func.sum(OutboundRecord.quantity)).scalar() or 0
    total_stock = db.session.query(db.func.sum(StockBatch.quantity)).scalar() or 0

    # 库存预警
    warning_items = []
    expired_items = []
    for c in Consumable.query.all():
        stock_status = c.stock_status
        expiry_status = c.expiry_status
        if stock_status in ('库存预警', '库存不足'):
            warning_items.append({
                'code': c.code, 'name': c.name,
                'total_stock': c.total_stock,
                'stock_warning_value': c.stock_warning_value,
                'status': stock_status,
            })
        if expiry_status in ('近效期', '已过期'):
            expired_items.append({
                'code': c.code, 'name': c.name,
                'expiry_status': expiry_status,
            })

    # 科室出库统计
    dept_stats = db.session.query(
        OutboundRecord.department,
        db.func.sum(OutboundRecord.quantity).label('total')
    ).filter(OutboundRecord.department.isnot(None), OutboundRecord.department != '') \
     .group_by(OutboundRecord.department).all()
    dept_data = [{'department': d, 'total': int(t)} for d, t in dept_stats]

    # 近期出入库趋势（近30天，按日聚合）
    from datetime import timedelta
    today = date.today()
    trend_start = today - timedelta(days=29)
    trend_days = []
    inbound_trend = []
    outbound_trend = []
    for i in range(30):
        d = trend_start + timedelta(days=i)
        d_str = d.strftime('%Y-%m-%d')
        trend_days.append(d_str)
        ib = db.session.query(db.func.coalesce(db.func.sum(InboundRecord.quantity), 0)) \
            .filter(InboundRecord.inbound_time >= d_str,
                    InboundRecord.inbound_time < (d + timedelta(days=1)).strftime('%Y-%m-%d')) \
            .scalar() or 0
        ob = db.session.query(db.func.coalesce(db.func.sum(OutboundRecord.quantity), 0)) \
            .filter(OutboundRecord.outbound_time >= d_str,
                    OutboundRecord.outbound_time < (d + timedelta(days=1)).strftime('%Y-%m-%d')) \
            .scalar() or 0
        inbound_trend.append(int(ib))
        outbound_trend.append(int(ob))

    # 最近盘点摘要
    last_check = InventoryCheck.query.order_by(InventoryCheck.check_date.desc()).first()
    check_summary = None
    if last_check:
        items = last_check.items.all()
        diff_items = [i for i in items if i.difference != 0]
        check_summary = {
            'id': last_check.id,
            'check_date': last_check.check_date.strftime('%Y-%m-%d'),
            'status': last_check.status,
            'total_items': len(items),
            'diff_items': len(diff_items),
        }

    return jsonify({
        'total_consumables': total_consumables,
        'total_inbound': int(total_inbound),
        'total_outbound': int(total_outbound),
        'total_stock': int(total_stock),
        'warning_count': len(warning_items),
        'expired_count': len(expired_items),
        'warning_items': warning_items[:10],
        'expired_items': expired_items[:10],
        'dept_stats': dept_data,
        'trend': {
            'days': trend_days,
            'inbound': inbound_trend,
            'outbound': outbound_trend,
        },
        'check_summary': check_summary,
    })


# ======================== 工具函数 ========================

def _parse_date(value):
    """解析日期字符串"""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            # Excel 数字日期格式
            from datetime import timedelta
            return date(1899, 12, 30) + timedelta(days=int(value))
        s = str(value).split('.')[0].strip()
        for fmt in ('%Y-%m-%d', '%Y%m%d', '%Y/%m/%d'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def _parse_datetime(value):
    """解析日期时间字符串"""
    if not value:
        return datetime.now()
    try:
        s = str(value).strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y%m%d'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    except Exception:
        pass
    return datetime.now()