# 医院耗材管理系统

一套面向医院科室的耗材库存管理系统，支持 Windows / macOS 单机部署、Excel 批量导入导出。

## 功能一览

| 模块 | 功能 |
|------|------|
| 🔍 仪表盘 | 耗材品种数、库存总量、库存预警、效期预警、科室出库统计 |
| 📦 耗材管理 | 增删改查、模糊搜索、分页 |
| 📥 入库管理 | 入库登记、批次管理、自动累加库存 |
| 📤 出库管理 | 出库登记、先进先出(FIFO)扣减、科室领用 |
| 📊 库存查询 | 库存总览、库存预警/效期预警筛选、批次明细 |
| 📑 Excel功能 | 批量导入耗材/入库记录、导出耗材/库存/入库/出库、模板下载 |

## 快速启动

### 方式一：macOS / Linux 启动
```bash
# 首次运行会自动安装依赖
./start.sh
# 浏览器自动打开 http://localhost:5000
```

### 方式二：Windows 双击启动
1. 确保已安装 Python 3.9+
2. 双击 `start.bat`
3. 浏览器自动打开 http://localhost:5000

### 方式三：命令行启动
```bash
pip install -r requirements.txt
python app.py
```
浏览器访问 http://localhost:5000

### 方式四：打包为 exe（Windows，无需 Python 环境）
```bash
# 在 Windows 上运行
build.bat
# 输出在 dist/医院耗材管理系统/ 目录下
```

## 数据库

- 使用 SQLite，数据文件位于 `database/erp.db`
- 首次启动自动创建数据库表
- 支持备份：直接复制 `database/erp.db` 文件即可

## 项目结构

```
erp_sys/
├── app.py              # Flask 主入口
├── config.py           # 配置文件
├── requirements.txt    # Python 依赖
├── start.sh            # macOS/Linux 启动脚本
├── start.bat           # Windows 启动脚本
├── build.bat           # PyInstaller 打包脚本
├── models/
│   └── models.py       # 数据模型
├── routes/
│   ├── consumable.py   # 耗材 CRUD API
│   ├── stock.py        # 入库/出库/库存/仪表盘 API
│   └── excel.py        # Excel 导入导出 API
├── static/
│   ├── css/style.css
│   └── js/app.js       # Vue 3 前端
├── templates/
│   └── index.html      # 单页应用
└── database/
    └── erp.db          # SQLite 数据（自动生成）
```

## 技术栈

- **后端**: Python + Flask + SQLAlchemy
- **数据库**: SQLite（零配置）
- **前端**: Vue 3 + Element Plus（CDN 加载，无需构建）
- **Excel**: openpyxl + pandas
- **部署**: PyInstaller 打包为 .exe