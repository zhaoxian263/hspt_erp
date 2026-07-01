import io
import os
from datetime import datetime, date
from flask import Blueprint, request, jsonify, send_file
from models import db, Consumable, StockBatch, InboundRecord, OutboundRecord

excel_bp = Blueprint('excel', __name__)


@excel_bp.route('/template/consumable', methods=['GET'])
def download_consumable_template():
    """下载耗材基础信息导入模板"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '基础信息'
    headers = ['耗材编号', '耗材名称', '类别', '品牌名称', '生产厂家', '规格型号', '单位',
               '存放位置', '期初库存', '期初生产日期', '期初失效日期', '库存预警值', '近效期预警天数', '备注']
    ws.append(headers)

    # 示例数据
    ws.append(['HC2027070101', '医用外科口罩', '防护用品', '海马医森', '宏冠医疗', '无菌型挂耳式', '个', 'A区1号架', 0, '', '', 100, 60, ''])
    ws.append(['HC2027070102', '密闭式静脉留置针', '注射穿刺类', '競玛', '碧迪医疗', '22G×1.00IN', '支', 'B区2号架', 0, '', '', 50, 90, ''])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name='耗材导入模板.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/template/inbound', methods=['GET'])
def download_inbound_template():
    """下载入库记录导入模板"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '入库记录'
    headers = ['耗材编号', '批号', '生产日期', '失效日期', '入库数量', '经办人', '存放位置', '入库时间', '备注']
    ws.append(headers)

    # 示例数据
    ws.append(['HC2027070101', 'LOT20270101', '2026-06-01', '2028-06-01', 100, '张三', 'A区1号架', '2026-06-29 10:30:00', ''])
    ws.append(['HC2027070102', 'LOT20270102', '2026-06-15', '2029-06-15', 50, '李四', 'B区2号架', '2026-06-28 14:00:00', ''])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name='入库记录导入模板.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/template/outbound', methods=['GET'])
def download_outbound_template():
    """下载出库记录导入模板"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '出库记录'
    headers = ['耗材编号', '批号', '出库数量', '领用人', '领用科室', '经办人', '出库时间', '备注']
    ws.append(headers)

    # 示例数据
    ws.append(['HC2027070101', 'LOT20270101', 10, '张三', '门诊检验科', '李四', '2026-06-29 10:30:00', ''])
    ws.append(['HC2027070102', 'LOT20270102', 5, '王五', '住院部', '赵六', '2026-06-28 14:00:00', ''])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name='出库记录导入模板.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/import/consumable', methods=['POST'])
def import_consumables():
    """批量导入耗材基础信息"""
    if 'file' not in request.files:
        return jsonify({'error': '未找到上传文件'}), 400

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': '仅支持 .xlsx / .xls 格式'}), 400

    update_mode = request.form.get('mode', 'skip')  # skip=跳过已有, update=更新已有

    import pandas as pd
    try:
        df = pd.read_excel(file, sheet_name=0, dtype=str)
        df = df.fillna('')
    except Exception as e:
        return jsonify({'error': f'Excel 解析失败: {str(e)}'}), 400

    # 列名映射（兼容多种命名）
    col_map = {
        '耗材编号': ['耗材编号', '编号', 'code'],
        '耗材名称': ['耗材名称', '名称', 'name'],
        '类别': ['类别', '分类', 'category'],
        '品牌名称': ['品牌名称', '品牌', 'brand'],
        '生产厂家': ['生产厂家', '厂家', 'manufacturer'],
        '规格型号': ['规格型号', '规格', 'specification'],
        '单位': ['单位', 'unit'],
        '存放位置': ['存放位置', '位置', 'storage_location'],
        '期初库存': ['期初库存', '初始库存', 'initial_stock'],
        '期初生产日期': ['期初生产日期', 'initial_production_date'],
        '期初失效日期': ['期初失效日期', 'initial_expiry_date'],
        '库存预警值': ['库存预警值', '预警值', 'stock_warning_value'],
        '近效期预警天数': ['近效期预警天数', '效期预警天数', '预警时间（天）', 'expiry_warning_days'],
        '备注': ['备注', 'remark'],
    }

    # 匹配列名
    col_idx = {}
    columns_lower = {c.lower().strip(): c for c in df.columns}
    for target, aliases in col_map.items():
        for alias in aliases:
            if alias.lower() in columns_lower:
                col_idx[target] = columns_lower[alias.lower()]
                break

    if '耗材编号' not in col_idx or '耗材名称' not in col_idx:
        return jsonify({'error': 'Excel缺少必填列：耗材编号、耗材名称'}), 400

    # 日期解析工具
    from routes.stock import _parse_date

    success = 0
    skipped = 0
    updated = 0
    errors = []

    # 预加载所有已有编号，用于重复校验
    existing_codes = set(c.code for c in Consumable.query.all())
    # 追踪文件内已处理的编号，防止文件内部编号重复
    seen_codes_in_file = set()

    def _safe_int(val, default=0):
        try:
            return int(float(val)) if val else default
        except (ValueError, TypeError):
            return default

    for i, row in df.iterrows():
        row_num = i + 2  # Excel行号（1-indexed + 头行）
        try:
            code = str(row.get(col_idx.get('耗材编号'), '')).strip()
            name = str(row.get(col_idx.get('耗材名称'), '')).strip()
            if not code or not name:
                errors.append(f'第{row_num}行: 编号或名称为空，跳过')
                continue

            # 校验：文件内编号重复
            if code in seen_codes_in_file:
                errors.append(f'第{row_num}行: 耗材编号 {code} 在文件内重复，跳过')
                continue
            seen_codes_in_file.add(code)

            existing = Consumable.query.filter_by(code=code).first()
            if existing:
                if update_mode == 'skip':
                    skipped += 1
                    continue
                elif update_mode == 'update':
                    # 更新已有记录（留空字段不修改）
                    if '耗材名称' in col_idx:
                        val = str(row.get(col_idx['耗材名称'], '')).strip()
                        if val:
                            existing.name = val
                    if '类别' in col_idx:
                        val = str(row.get(col_idx['类别'], '')).strip()
                        if val:
                            existing.category = val
                    if '品牌名称' in col_idx:
                        val = str(row.get(col_idx['品牌名称'], '')).strip()
                        if val:
                            existing.brand = val
                    if '生产厂家' in col_idx:
                        val = str(row.get(col_idx['生产厂家'], '')).strip()
                        if val:
                            existing.manufacturer = val
                    if '规格型号' in col_idx:
                        val = str(row.get(col_idx['规格型号'], '')).strip()
                        if val:
                            existing.specification = val
                    if '单位' in col_idx:
                        val = str(row.get(col_idx['单位'], '')).strip()
                        if val:
                            existing.unit = val
                    if '存放位置' in col_idx:
                        val = str(row.get(col_idx['存放位置'], '')).strip()
                        if val:
                            existing.storage_location = val
                    if '期初库存' in col_idx:
                        val = row.get(col_idx['期初库存'], '')
                        if val:
                            existing.initial_stock = _safe_int(val, 0)
                    # 期初生产日期/失效日期：同步到期初库存批次
                    init_prod_date = _parse_date(row.get(col_idx.get('期初生产日期'))) if '期初生产日期' in col_idx else None
                    init_exp_date = _parse_date(row.get(col_idx.get('期初失效日期'))) if '期初失效日期' in col_idx else None
                    if init_prod_date or init_exp_date:
                        init_batch = StockBatch.query.filter_by(
                            consumable_id=existing.id, batch_number='期初库存'
                        ).first()
                        if init_batch:
                            if init_prod_date:
                                init_batch.production_date = init_prod_date
                            if init_exp_date:
                                init_batch.expiry_date = init_exp_date
                    if '库存预警值' in col_idx:
                        val = row.get(col_idx['库存预警值'], '')
                        if val:
                            existing.stock_warning_value = _safe_int(val, existing.stock_warning_value)
                    if '近效期预警天数' in col_idx:
                        val = row.get(col_idx['近效期预警天数'], '')
                        if val:
                            existing.expiry_warning_days = _safe_int(val, existing.expiry_warning_days)
                    if '备注' in col_idx:
                        val = str(row.get(col_idx['备注'], '')).strip()
                        if val:
                            existing.remark = val
                    updated += 1
                    continue
            else:
                # 新增
                c = Consumable(code=code, name=name)
                if '类别' in col_idx:
                    c.category = str(row.get(col_idx['类别'], '')).strip()
                if '品牌名称' in col_idx:
                    c.brand = str(row.get(col_idx['品牌名称'], '')).strip()
                if '生产厂家' in col_idx:
                    c.manufacturer = str(row.get(col_idx['生产厂家'], '')).strip()
                if '规格型号' in col_idx:
                    c.specification = str(row.get(col_idx['规格型号'], '')).strip()
                if '单位' in col_idx:
                    c.unit = str(row.get(col_idx['单位'], '')).strip()
                if '存放位置' in col_idx:
                    c.storage_location = str(row.get(col_idx['存放位置'], '')).strip()
                if '期初库存' in col_idx:
                    c.initial_stock = _safe_int(row.get(col_idx['期初库存'], '0'), 0)
                if '库存预警值' in col_idx:
                    c.stock_warning_value = _safe_int(row.get(col_idx['库存预警值'], '0'), 0)
                if '近效期预警天数' in col_idx:
                    c.expiry_warning_days = _safe_int(row.get(col_idx['近效期预警天数'], '0'), 0)
                if '备注' in col_idx:
                    c.remark = str(row.get(col_idx['备注'], '')).strip()
                db.session.add(c)
                db.session.flush()  # 先 flush 以获取 c.id
                # 期初库存 > 0 时创建期初库存批次
                if c.initial_stock and c.initial_stock > 0:
                    init_prod_date = _parse_date(row.get(col_idx.get('期初生产日期'))) if '期初生产日期' in col_idx else None
                    init_exp_date = _parse_date(row.get(col_idx.get('期初失效日期'))) if '期初失效日期' in col_idx else None
                    batch = StockBatch(
                        consumable_id=c.id,
                        batch_number='期初库存',
                        quantity=c.initial_stock,
                        production_date=init_prod_date,
                        expiry_date=init_exp_date,
                        storage_location=c.storage_location,
                        remark='系统自动创建（期初库存）',
                    )
                    db.session.add(batch)
                success += 1
        except Exception as e:
            errors.append(f'第{row_num}行: {str(e)}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'数据库保存失败: {str(e)}'}), 500

    return jsonify({
        'success': success,
        'skipped': skipped,
        'updated': updated,
        'errors': errors[:20],
    })


@excel_bp.route('/export/consumable', methods=['GET'])
def export_consumables():
    """导出耗材基础信息为 Excel"""
    import openpyxl
    keyword = request.args.get('keyword', '').strip()
    query = Consumable.query
    if keyword:
        query = query.filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
            )
        )
    items = query.order_by(Consumable.code).all()

    wb = openpyxl.Workbook()
    # Sheet 1: 基础信息
    ws1 = wb.active
    ws1.title = '基础信息'
    headers1 = ['序号', '耗材编号', '耗材名称', '类别', '品牌名称', '生产厂家', '规格型号',
                '单位', '存放位置', '期初库存', '期初生产日期', '期初失效日期',
                '库存预警值', '近效期预警天数', '备注']
    ws1.append(headers1)
    for idx, c in enumerate(items, 1):
        # 查询期初库存批次的生产日期和失效日期
        init_batch = StockBatch.query.filter_by(
            consumable_id=c.id, batch_number='期初库存'
        ).first()
        init_prod = init_batch.production_date.strftime('%Y-%m-%d') if init_batch and init_batch.production_date else ''
        init_exp = init_batch.expiry_date.strftime('%Y-%m-%d') if init_batch and init_batch.expiry_date else ''
        ws1.append([idx, c.code, c.name, c.category, c.brand, c.manufacturer, c.specification,
                    c.unit, c.storage_location, c.initial_stock or 0,
                    init_prod, init_exp,
                    c.stock_warning_value, c.expiry_warning_days, c.remark])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'耗材基础信息_{date.today().strftime("%Y%m%d")}.xlsx'
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/export/inventory', methods=['GET'])
def export_inventory():
    """导出库存总览为 Excel"""
    import openpyxl
    items = Consumable.query.order_by(Consumable.code).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '库存总览'
    headers = ['序号', '耗材编号', '耗材名称', '类别', '规格型号', '生产厂家', '存放位置',
               '入库数量', '出库数量', '当前库存', '库存预警值', '库存状态',
               '近效期预警天数', '效期状态']
    ws.append(headers)
    for idx, c in enumerate(items, 1):
        d = c.to_dict(include_stock=True)
        ws1_data = [idx, c.code, c.name, c.category or '', c.specification, c.manufacturer,
                    c.storage_location or '',
                   d['total_inbound'], d['total_outbound'], d['total_stock'],
                   c.stock_warning_value, d['stock_status'],
                   c.expiry_warning_days, d['expiry_status']]
        ws.append(ws1_data)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'库存总览_{date.today().strftime("%Y%m%d")}.xlsx'
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/export/inbound', methods=['GET'])
def export_inbound():
    """导出入库记录为 Excel"""
    import openpyxl
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = InboundRecord.query
    if start_date:
        query = query.filter(InboundRecord.inbound_time >= start_date)
    if end_date:
        query = query.filter(InboundRecord.inbound_time <= end_date + ' 23:59:59')
    records = query.order_by(InboundRecord.inbound_time.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '入库记录'
    ws.append(['序号', '入库单号', '耗材编号', '耗材名称', '规格型号', '批号',
               '生产日期', '失效日期', '入库数量', '经办人', '存放位置', '入库时间', '备注'])
    for idx, r in enumerate(records, 1):
        d = r.to_dict(include_consumable=True)
        ws.append([idx, r.document_number or '', d.get('consumable_code', ''), d.get('consumable_name', ''),
                   d.get('consumable_spec', ''), r.batch_number,
                   d.get('production_date', ''), d.get('expiry_date', ''),
                   r.quantity, r.operator, r.storage_location or '', d.get('inbound_time', ''), r.remark])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'入库记录_{date.today().strftime("%Y%m%d")}.xlsx'
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/export/outbound', methods=['GET'])
def export_outbound():
    """导出出库记录为 Excel"""
    import openpyxl
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = OutboundRecord.query
    if start_date:
        query = query.filter(OutboundRecord.outbound_time >= start_date)
    if end_date:
        query = query.filter(OutboundRecord.outbound_time <= end_date + ' 23:59:59')
    records = query.order_by(OutboundRecord.outbound_time.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '出库记录'
    ws.append(['序号', '出库单号', '耗材编号', '耗材名称', '规格型号', '批号',
               '出库数量', '领用人', '领用科室', '经办人', '出库时间', '备注'])
    for idx, r in enumerate(records, 1):
        d = r.to_dict(include_consumable=True)
        ws.append([idx, r.document_number or '', d.get('consumable_code', ''), d.get('consumable_name', ''),
                   d.get('consumable_spec', ''), r.batch_number,
                   r.quantity, r.recipient, r.department,
                   r.operator, d.get('outbound_time', ''), r.remark])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'出库记录_{date.today().strftime("%Y%m%d")}.xlsx'
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/export/expiry-query', methods=['GET'])
def export_expiry_query():
    """导出效期查询为 Excel"""
    import openpyxl
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '').strip()
    category = request.args.get('category', '').strip()

    # 复用与 expiry_query 相同的查询逻辑，但不分页
    query = StockBatch.query.filter(StockBatch.quantity > 0)

    if keyword:
        query = query.join(Consumable, StockBatch.consumable_id == Consumable.id).filter(
            db.or_(Consumable.code.contains(keyword), Consumable.name.contains(keyword))
        )
    else:
        query = query.join(Consumable, StockBatch.consumable_id == Consumable.id)

    if category:
        query = query.filter(Consumable.category == category)

    query = query.order_by(StockBatch.expiry_date.asc().nullslast())

    batches = query.all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '效期查询'
    headers = ['序号', '耗材编号', '耗材名称', '类别', '批次', '存放位置',
               '生产日期', '失效日期', '效期状态', '当前库存']
    ws.append(headers)
    idx = 0
    for batch in batches:
        batch_status = batch.expiry_status
        # 效期状态过滤
        if status == 'near_expiry' and batch_status != '近效期':
            continue
        if status == 'expired' and batch_status != '已过期':
            continue
        idx += 1
        consumable = batch.consumable
        ws.append([
            idx,
            consumable.code if consumable else '',
            consumable.name if consumable else '',
            consumable.category if consumable else '',
            batch.batch_number or '-',
            batch.storage_location or '-',
            batch.production_date.strftime('%Y-%m-%d') if batch.production_date else '-',
            batch.expiry_date.strftime('%Y-%m-%d') if batch.expiry_date else '-',
            batch_status,
            batch.quantity,
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'效期查询_{date.today().strftime("%Y%m%d")}.xlsx'
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@excel_bp.route('/import/inbound', methods=['POST'])
def import_inbound():
    """批量导入入库记录"""
    if 'file' not in request.files:
        return jsonify({'error': '未找到上传文件'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': '仅支持 .xlsx / .xls 格式'}), 400

    import pandas as pd
    try:
        df = pd.read_excel(file, sheet_name=0, dtype=str)
        df = df.fillna('')
    except Exception as e:
        return jsonify({'error': f'Excel 解析失败: {str(e)}'}), 400

    col_map = {
        '耗材编号': ['耗材编号', '编号', 'code'],
        '批号': ['批号', 'batch_number'],
        '生产日期': ['生产日期', 'production_date'],
        '失效日期': ['失效日期', '有效期至', '有效期', 'expiry_date'],
        '入库数量': ['入库数量', '数量', 'quantity'],
        '经办人': ['经办人', 'operator'],
        '存放位置': ['存放位置', '位置', 'storage_location'],
        '入库时间': ['入库时间', 'inbound_time'],
        '备注': ['备注', 'remark'],
    }
    col_idx = {}
    columns_lower = {c.lower().strip(): c for c in df.columns}
    for target, aliases in col_map.items():
        for alias in aliases:
            if alias.lower() in columns_lower:
                col_idx[target] = columns_lower[alias.lower()]
                break

    if '耗材编号' not in col_idx or '入库数量' not in col_idx:
        return jsonify({'error': 'Excel缺少必填列：耗材编号、入库数量'}), 400

    from routes.stock import _parse_date, _parse_datetime, _generate_document_number
    success = 0
    errors = []

    # 预加载所有耗材编号映射，避免逐行查询
    all_consumables = {c.code: c for c in Consumable.query.all()}

    for i, row in df.iterrows():
        row_num = i + 2
        try:
            code = str(row.get(col_idx.get('耗材编号'), '')).strip()
            quantity_val = row.get(col_idx.get('入库数量'), '0')
            try:
                quantity = int(float(str(quantity_val)))
            except (ValueError, TypeError):
                errors.append(f'第{row_num}行: 数量格式错误')
                continue

            consumable = all_consumables.get(code)
            if not consumable:
                errors.append(f'第{row_num}行: 耗材编号 {code} 不存在')
                continue

            batch_number = str(row.get(col_idx.get('批号'), '')).strip()
            production_date = _parse_date(row.get(col_idx.get('生产日期')))
            expiry_date = _parse_date(row.get(col_idx.get('失效日期')))
            operator = str(row.get(col_idx.get('经办人'), '')).strip()
            storage_location = str(row.get(col_idx.get('存放位置'), '')).strip()
            inbound_time = _parse_datetime(row.get(col_idx.get('入库时间')))
            remark = str(row.get(col_idx.get('备注'), '')).strip()

            # 自动生成入库单号
            document_number = _generate_document_number('RK')

            # 创建入库记录
            record = InboundRecord(
                consumable_id=consumable.id,
                document_number=document_number,
                batch_number=batch_number,
                production_date=production_date,
                expiry_date=expiry_date,
                quantity=quantity,
                operator=operator,
                storage_location=storage_location,
                inbound_time=inbound_time,
                remark=remark,
            )
            db.session.add(record)

            # 更新库存批次
            batch = StockBatch.query.filter_by(
                consumable_id=consumable.id,
                batch_number=batch_number,
            ).first()
            if batch:
                batch.quantity += quantity
            else:
                batch = StockBatch(
                    consumable_id=consumable.id,
                    batch_number=batch_number,
                    production_date=production_date,
                    expiry_date=expiry_date,
                    quantity=quantity,
                    storage_location=storage_location,
                )
                db.session.add(batch)
            success += 1
        except Exception as e:
            errors.append(f'第{row_num}行: {str(e)}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

    return jsonify({'success': success, 'errors': errors[:20]})


@excel_bp.route('/import/outbound', methods=['POST'])
def import_outbound():
    """批量导出出库记录"""
    if 'file' not in request.files:
        return jsonify({'error': '未找到上传文件'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': '仅支持 .xlsx / .xls 格式'}), 400

    import pandas as pd
    try:
        df = pd.read_excel(file, sheet_name=0, dtype=str)
        df = df.fillna('')
    except Exception as e:
        return jsonify({'error': f'Excel 解析失败: {str(e)}'}), 400

    col_map = {
        '耗材编号': ['耗材编号', '编号', 'code'],
        '批号': ['批号', 'batch_number'],
        '出库数量': ['出库数量', '数量', 'quantity'],
        '领用人': ['领用人', 'recipient'],
        '领用科室': ['领用科室', '科室', 'department'],
        '经办人': ['经办人', 'operator'],
        '出库时间': ['出库时间', 'outbound_time'],
        '备注': ['备注', 'remark'],
    }
    col_idx = {}
    columns_lower = {c.lower().strip(): c for c in df.columns}
    for target, aliases in col_map.items():
        for alias in aliases:
            if alias.lower() in columns_lower:
                col_idx[target] = columns_lower[alias.lower()]
                break

    if '耗材编号' not in col_idx or '出库数量' not in col_idx:
        return jsonify({'error': 'Excel缺少必填列：耗材编号、出库数量'}), 400

    from routes.stock import _parse_datetime, _generate_document_number
    success = 0
    errors = []

    # 预加载所有耗材编号映射
    all_consumables = {c.code: c for c in Consumable.query.all()}

    for i, row in df.iterrows():
        row_num = i + 2
        try:
            code = str(row.get(col_idx.get('耗材编号'), '')).strip()
            quantity_val = row.get(col_idx.get('出库数量'), '0')
            try:
                quantity = int(float(str(quantity_val)))
            except (ValueError, TypeError):
                errors.append(f'第{row_num}行: 数量格式错误')
                continue

            consumable = all_consumables.get(code)
            if not consumable:
                errors.append(f'第{row_num}行: 耗材编号 {code} 不存在')
                continue

            batch_number = str(row.get(col_idx.get('批号'), '')).strip()
            recipient = str(row.get(col_idx.get('领用人'), '')).strip()
            department = str(row.get(col_idx.get('领用科室'), '')).strip()
            operator = str(row.get(col_idx.get('经办人'), '')).strip()
            outbound_time = _parse_datetime(row.get(col_idx.get('出库时间')))
            remark = str(row.get(col_idx.get('备注'), '')).strip()

            # 自动生成出库单号
            document_number = _generate_document_number('CK')

            # 创建出库记录
            record = OutboundRecord(
                consumable_id=consumable.id,
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

            # 扣减库存批次
            from models import StockBatch
            if batch_number:
                batch = StockBatch.query.filter_by(
                    consumable_id=consumable.id,
                    batch_number=batch_number,
                ).first()
                if batch and batch.quantity >= quantity:
                    batch.quantity -= quantity
                    success += 1
                else:
                    errors.append(f'第{row_num}行: 批号 {batch_number} 库存不足')
            else:
                # 自动先进先出
                batches = StockBatch.query.filter(
                    StockBatch.consumable_id == consumable.id,
                    StockBatch.quantity > 0
                ).order_by(StockBatch.expiry_date, StockBatch.id).all()
                remaining = quantity
                for batch in batches:
                    if remaining <= 0:
                        break
                    deduct = min(batch.quantity, remaining)
                    batch.quantity -= deduct
                    remaining -= deduct
                if remaining > 0:
                    errors.append(f'第{row_num}行: 库存不足，缺少 {remaining} 件')
                else:
                    success += 1
        except Exception as e:
            errors.append(f'第{row_num}行: {str(e)}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

    return jsonify({'success': success, 'errors': errors[:20]})