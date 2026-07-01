// 设置 Day.js 为中文
if (window.dayjs) {
  window.dayjs.locale('zh-cn');
}

// 确保 Element Plus 命令式 API 可用
const ElMessage = window.ElMessage || ElementPlus.ElMessage;
const ElMessageBox = window.ElMessageBox || ElementPlus.ElMessageBox;

const API = {
  // 耗材
  consumables: '/api/consumables',
  consumableAll: '/api/consumables/all',
  consumable: id => `/api/consumables/${id}`,
  // 入库
  inbound: '/api/stock/inbound',
  inboundDel: id => `/api/stock/inbound/${id}`,
  inboundPrint: id => `/api/stock/inbound/${id}/print`,
  // 出库
  outbound: '/api/stock/outbound',
  outboundDel: id => `/api/stock/outbound/${id}`,
  outboundPrint: id => `/api/stock/outbound/${id}/print`,
  // 科室
  departments: '/api/departments',
  department: id => `/api/departments/${id}`,
  departmentsInit: '/api/departments/init',
  // 类别
  categories: '/api/categories',
  category: id => `/api/categories/${id}`,
  // 人员
  staff: '/api/staff',
  staffItem: id => `/api/staff/${id}`,
  // 盘点
  inventoryChecks: '/api/inventory-checks',
  inventoryCheck: id => `/api/inventory-checks/${id}`,
  inventoryCheckConfirm: id => `/api/inventory-checks/${id}/confirm`,
  // 库存
  inventory: '/api/stock/inventory',
  batches: '/api/stock/batches',
  dashboard: '/api/stock/dashboard',
  periodInventory: '/api/stock/period-inventory',
  expiryQuery: '/api/stock/expiry-query',
  // Excel
  tplConsumable: '/api/excel/template/consumable',
  tplInbound: '/api/excel/template/inbound',
  tplOutbound: '/api/excel/template/outbound',
  importOutbound: '/api/excel/import/outbound',
  importConsumable: '/api/excel/import/consumable',
  importInbound: '/api/excel/import/inbound',
  exportConsumable: '/api/excel/export/consumable',
  exportInventory: '/api/excel/export/inventory',
  exportInbound: '/api/excel/export/inbound',
  exportOutbound: '/api/excel/export/outbound',
  exportExpiryQuery: '/api/excel/export/expiry-query',
};

// 下载/导出：构建绝对URL后直接让浏览器打开下载
function downloadUrl(path) {
  const baseUrl = window.location.origin;
  const fullUrl = path.startsWith('/') ? baseUrl + path : baseUrl + '/' + path;
  window.location.href = fullUrl;
}

// 科室列表（从后端动态加载）
let deptOptions = [];
let _deptLoaded = loadDeptOptions();
async function loadDeptOptions() {
  try {
    const res = await fetch(API.departments);
    let data = await res.json();
    if (Array.isArray(data) && data.length === 0) {
      await fetch(API.departmentsInit, { method: 'POST' });
      const res2 = await fetch(API.departments);
      data = await res2.json();
    }
    deptOptions = data;
  } catch (e) { console.error('加载科室列表失败', e); }
}

// 类别列表（从后端动态加载）
let categoryOptions = [];
let _categoryLoaded = loadCategoryOptions();
async function loadCategoryOptions() {
  try {
    const res = await fetch(API.categories);
    categoryOptions = await res.json();
  } catch (e) { console.error('加载类别列表失败', e); }
}

// 打印单据（打开新窗口打印）
function printDocument(title, htmlContent) {
  const win = window.open('', '_blank');
  if (!win) { ElMessage.error('请允许弹出窗口以打印'); return; }
  win.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${title}</title>
    <style>
      body { font-family: 'Microsoft YaHei', sans-serif; padding: 30px; color: #333; }
      h2 { text-align: center; margin-bottom: 20px; }
      .print-info { margin: 8px 0; font-size: 14px; display: flex; flex-wrap: wrap; }
      .print-info span { display: inline-block; min-width: 280px; margin-right: 20px; }
      table { width: 100%; border-collapse: collapse; margin: 16px 0; }
      th, td { border: 1px solid #333; padding: 8px 10px; text-align: center; font-size: 13px; }
      th { background: #f0f0f0; }
      .print-footer { margin-top: 40px; display: flex; justify-content: space-around; font-size: 14px; }
      @media print { body { padding: 0; } }
    </style></head><body>${htmlContent}
    <script>window.onload=function(){window.print();}<\/script></body></html>`);
  win.document.close();
}

// ======================== 首页仪表盘 ========================
const DashboardPage = {
  data() {
    return { stats: null, loading: true };
  },
  async mounted() {
    try {
      const res = await fetch(API.dashboard);
      this.stats = await res.json();
    } catch (e) { console.error(e); }
    this.loading = false;
    // 延迟渲染趋势图
    this.$nextTick(() => { setTimeout(() => this.renderTrendChart(), 200); });
  },
  methods: {
    renderTrendChart() {
      if (!this.stats || !this.stats.trend || !window.echarts) return;
      const chartDom = document.getElementById('trend-chart');
      if (!chartDom) return;
      const chart = echarts.init(chartDom);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['入库', '出库'], top: 0 },
        grid: { top: 35, left: 50, right: 20, bottom: 30 },
        xAxis: { type: 'category', data: this.stats.trend.days.map(d => d.slice(5)), axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', minInterval: 1 },
        series: [
          { name: '入库', type: 'bar', data: this.stats.trend.inbound, itemStyle: { color: '#67C23A' } },
          { name: '出库', type: 'bar', data: this.stats.trend.outbound, itemStyle: { color: '#409EFF' } },
        ]
      });
      window.addEventListener('resize', () => chart.resize());
    },
  },
  template: `
    <div v-loading="loading">
      <h3 class="page-title">仪表盘</h3>
      <div class="dashboard-grid" v-if="stats">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.total_consumables }}</div><div class="stat-label">耗材品种数</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value success-value">{{ stats.total_stock }}</div><div class="stat-label">库存总量</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value" style="color:#67C23A">{{ stats.total_inbound }}</div><div class="stat-label">累计入库</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value" style="color:#409EFF">{{ stats.total_outbound }}</div><div class="stat-label">累计出库</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value warning-value">{{ stats.warning_count }}</div><div class="stat-label">库存预警</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value danger-value">{{ stats.expired_count }}</div><div class="stat-label">效期预警</div>
        </el-card>
      </div>
      <!-- 趋势图 -->
      <el-card shadow="hover" style="margin-bottom:20px" v-if="stats && stats.trend">
        <template #header><span>出入库趋势（近30天）</span></template>
        <div id="trend-chart" style="width:100%;height:300px"></div>
      </el-card>
      <el-row :gutter="20" v-if="stats">
        <el-col :span="8">
          <el-card shadow="hover" style="margin-bottom:20px">
            <template #header><span>库存预警</span></template>
            <el-table :data="stats.warning_items" size="small" empty-text="暂无预警">
              <el-table-column prop="code" label="编号" width="120" />
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="total_stock" label="当前库存" width="80" />
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{row}">
                  <el-tag :type="row.status==='库存不足'?'danger':'warning'" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" style="margin-bottom:20px">
            <template #header><span>效期预警</span></template>
            <el-table :data="stats.expired_items" size="small" empty-text="暂无预警">
              <el-table-column prop="code" label="编号" width="120" />
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="expiry_status" label="效期状态" width="80">
                <template #default="{row}">
                  <el-tag :type="row.expiry_status==='已过期'?'danger':'warning'" size="small">{{ row.expiry_status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="8">
          <!-- 盘点摘要 -->
          <el-card shadow="hover" style="margin-bottom:20px" v-if="stats.check_summary">
            <template #header><span>最近盘点</span></template>
            <div class="check-summary-info">
              <p>盘点日期：{{ stats.check_summary.check_date }}</p>
              <p>状态：{{ stats.check_summary.status === 'draft' ? '草稿' : '已确认' }}</p>
              <p>盘点项数：{{ stats.check_summary.total_items }}</p>
              <p>差异项数：<span :style="{color: stats.check_summary.diff_items > 0 ? '#E6A23C' : '#67C23A'}">{{ stats.check_summary.diff_items }}</span></p>
            </div>
          </el-card>
          <el-card shadow="hover" style="margin-bottom:20px">
            <template #header><span>科室出库统计</span></template>
            <el-table :data="stats.dept_stats" size="small" empty-text="暂无数据">
              <el-table-column prop="department" label="科室" />
              <el-table-column prop="total" label="出库数量" width="80" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </div>
  `
};

// ======================== 耗材管理 ========================
const ConsumablePage = {
  data() {
    return {
      items: [], total: 0, page: 1, pageSize: 20, keyword: '', categoryFilter: '',
      dialogVisible: false, dialogTitle: '新增耗材', form: {}, isEdit: false,
      categoryOptions: [],
    };
  },
  async created() {
    await _categoryLoaded;
    this.categoryOptions = categoryOptions;
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword, include_stock: 'true' });
      if (this.categoryFilter) params.set('category', this.categoryFilter);
      const res = await fetch(`${API.consumables}?${params}`);
      const data = await res.json();
      this.items = data.items; this.total = data.total;
    },
    onSearch() { this.page = 1; this.loadData(); },
    onPageChange(p) { this.page = p; this.loadData(); },
    openAdd() {
      this.isEdit = false; this.dialogTitle = '新增耗材';
      this.form = { code:'', name:'', brand:'', manufacturer:'', specification:'', unit:'', category:'', storage_location:'', initial_stock:0, initial_production_date:'', initial_expiry_date:'', stock_warning_value:0, expiry_warning_days:0, remark:'' };
      this.categoryOptions = categoryOptions;
      this.dialogVisible = true;
    },
    openEdit(row) {
      this.isEdit = true; this.dialogTitle = '编辑耗材'; this.form = { ...row };
      this.categoryOptions = categoryOptions;
      this.dialogVisible = true;
    },
    async saveForm() {
      if (!this.form.code || !this.form.name) { ElMessage.warning('编号和名称为必填'); return; }
      const url = this.isEdit ? API.consumable(this.form.id) : API.consumables;
      const method = this.isEdit ? 'PUT' : 'POST';
      const res = await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(this.form) });
      if (res.ok) { ElMessage.success(this.isEdit ? '耗材更新成功' : '耗材新增成功'); this.dialogVisible = false; this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error || '保存失败'); }
    },
    async del(row) {
      try { await ElMessageBox.confirm(`确定删除 "${row.name}" 吗？`, '提示', { type: 'warning' }); } catch { return; }
      const res = await fetch(API.consumable(row.id), { method: 'DELETE' });
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error || '删除失败'); }
    },
    stockTagType(s) { return s==='库存不足'?'danger': s==='库存预警'?'warning':'success'; },
    expiryTagType(s) { return s==='已过期'?'danger': s==='近效期'?'warning':'success'; },
    gotoExcel() { this.$router.push('/excel'); },
  },
  template: `
    <div>
      <h3 class="page-title">耗材管理</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="5"><el-input v-model="keyword" placeholder="编号/名称/品牌搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="4">
            <el-select v-model="categoryFilter" placeholder="类别筛选" clearable @change="onSearch" style="width:100%">
              <el-option v-for="c in categoryOptions" :key="c.id" :label="c.name" :value="c.name" />
            </el-select>
          </el-col>
          <el-col :span="8">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button type="success" @click="openAdd">新增耗材</el-button>
            <el-button @click="gotoExcel">Excel导入导出</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small" style="width:100%">
        <el-table-column prop="code" label="耗材编号" width="120" fixed />
        <el-table-column prop="name" label="耗材名称" min-width="140" />
        <el-table-column prop="category" label="类别" width="90" />
        <el-table-column prop="brand" label="品牌" width="80" />
        <el-table-column prop="specification" label="规格型号" width="120" />
        <el-table-column prop="unit" label="单位" width="55" />
        <el-table-column prop="storage_location" label="存放位置" width="100" />
        <el-table-column prop="total_stock" label="库存" width="60" />
        <el-table-column label="库存状态" width="80">
          <template #default="{row}">
            <el-tag v-if="row.stock_status" :type="stockTagType(row.stock_status)" size="small">{{ row.stock_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="效期状态" width="80">
          <template #default="{row}">
            <el-tag v-if="row.expiry_status" :type="expiryTagType(row.expiry_status)" size="small">{{ row.expiry_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="stock_warning_value" label="库存预警值" width="90" />
        <el-table-column prop="expiry_warning_days" label="效期预警值" width="90" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <el-dialog v-model="dialogVisible" :title="dialogTitle" width="720px" destroy-on-close>
        <el-form :model="form" label-width="100px" size="default">
          <el-divider content-position="left">基本信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="耗材编号" required><el-input v-model="form.code" :disabled="isEdit" placeholder="如 HC001" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="耗材名称" required><el-input v-model="form.name" placeholder="如 一次性注射器" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="类别">
              <el-select v-model="form.category" filterable allow-create placeholder="选择或输入类别" style="width:100%">
                <el-option v-for="c in categoryOptions" :key="c.id" :label="c.name" :value="c.name" />
              </el-select>
            </el-form-item></el-col>
            <el-col :span="12"><el-form-item label="单位"><el-input v-model="form.unit" placeholder="如 支、包、盒" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="品牌名称"><el-input v-model="form.brand" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="生产厂家"><el-input v-model="form.manufacturer" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="规格型号"><el-input v-model="form.specification" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="存放位置"><el-input v-model="form.storage_location" placeholder="如 1号库房-A区" /></el-form-item></el-col>
          </el-row>
          <el-divider content-position="left">库存设置</el-divider>
          <el-row :gutter="16">
            <el-col :span="8"><el-form-item label="期初库存"><el-input-number v-model="form.initial_stock" :min="0" :step="1" style="width:100%" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="库存预警值"><el-input-number v-model="form.stock_warning_value" :min="0" style="width:100%" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="效期预警天数"><el-input-number v-model="form.expiry_warning_days" :min="0" style="width:100%" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16" v-if="form.initial_stock > 0">
            <el-col :span="12"><el-form-item label="生产日期"><el-date-picker v-model="form.initial_production_date" type="date" value-format="YYYY-MM-DD" placeholder="期初库存生产日期" style="width:100%" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="失效日期"><el-date-picker v-model="form.initial_expiry_date" type="date" value-format="YYYY-MM-DD" placeholder="期初库存失效日期" style="width:100%" /></el-form-item></el-col>
          </el-row>
          <el-divider content-position="left">其他</el-divider>
          <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" placeholder="选填" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible=false">取消</el-button>
          <el-button type="primary" @click="saveForm">保存</el-button>
        </template>
      </el-dialog>
    </div>
  `
};

// ======================== 入库管理 ========================
const InboundPage = {
  data() {
    return {
      items: [], total: 0, page: 1, pageSize: 20, keyword: '',
      startDate: '', endDate: '',
      dialogVisible: false, form: {}, consumableList: [],
    };
  },
  async mounted() { this.loadData(); this.loadConsumables(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword });
      if (this.startDate) params.set('start_date', this.startDate);
      if (this.endDate) params.set('end_date', this.endDate);
      const res = await fetch(`${API.inbound}?${params}`);
      const data = await res.json(); this.items = data.items; this.total = data.total;
    },
    async loadConsumables() {
      const res = await fetch(API.consumableAll); this.consumableList = await res.json();
    },
    onSearch() { this.page = 1; this.loadData(); },
    onPageChange(p) { this.page = p; this.loadData(); },
    openAdd() {
      const now = new Date().toISOString().slice(0, 16);
      this.form = { consumable_id: null, batch_number: '', production_date: '', expiry_date: '', quantity: 1, operator: '', storage_location: '', inbound_time: now, remark: '' };
      this.dialogVisible = true;
    },
    gotoExcel() { this.$router.push('/excel'); },
    async saveForm() {
      if (!this.form.consumable_id || !this.form.quantity) { ElMessage.warning('请选择耗材并填写数量'); return; }
      const res = await fetch(API.inbound, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(this.form) });
      if (res.ok) { ElMessage.success('入库提交成功'); this.dialogVisible = false; this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error || '入库失败'); }
    },
    async del(row) {
      try { await ElMessageBox.confirm('确定删除该记录？库存将同步扣减', '提示', {type:'warning'}); } catch { return; }
      const res = await fetch(API.inboundDel(row.id), {method:'DELETE'});
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error); }
    },
    async printRecord(row) {
      try {
        const res = await fetch(API.inboundPrint(row.id));
        const data = await res.json();
        const html = `
          <h2>入库单</h2>
          <div class="print-info"><span>入库单号：${data.document_number || '-'}</span><span>入库时间：${data.inbound_time || '-'}</span></div>
          <div class="print-info"><span>经办人：${data.operator || '-'}</span><span>存放位置：${data.storage_location || '-'}</span></div>
          <div style="clear:both"></div>
          <table>
            <tr><th>耗材编号</th><th>耗材名称</th><th>规格型号</th><th>品牌</th><th>单位</th><th>批号</th><th>生产日期</th><th>失效日期</th><th>数量</th><th>备注</th></tr>
            <tr>
              <td>${data.consumable_code || ''}</td><td>${data.consumable_name || ''}</td>
              <td>${data.consumable_spec || ''}</td><td>${data.consumable_brand || ''}</td>
              <td>${data.consumable_unit || ''}</td><td>${data.batch_number || ''}</td>
              <td>${data.production_date || ''}</td><td>${data.expiry_date || ''}</td>
              <td>${data.quantity}</td><td>${data.remark || ''}</td>
            </tr>
          </table>
          <div class="print-footer"><span>经办人签字：__________</span><span>验收人签字：__________</span><span>日期：__________</span></div>`;
        printDocument('入库单 - ' + (data.document_number || ''), html);
      } catch(e) { ElMessage.error('获取打印数据失败'); }
    },
  },
  template: `
    <div>
      <h3 class="page-title">入库管理</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="5"><el-input v-model="keyword" placeholder="单号/编号/名称/批号搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="3"><el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width:100%" /></el-col>
          <el-col :span="3"><el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width:100%" /></el-col>
          <el-col :span="8">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button type="success" @click="openAdd">新增入库</el-button>
            <el-button @click="gotoExcel">Excel导入</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="document_number" label="入库单号" width="150" />
        <el-table-column prop="consumable_code" label="耗材编号" width="120" />
        <el-table-column prop="consumable_name" label="耗材名称" min-width="130" />
        <el-table-column prop="consumable_spec" label="规格型号" width="110" />
        <el-table-column prop="batch_number" label="批号" width="110" />
        <el-table-column prop="production_date" label="生产日期" width="95" />
        <el-table-column prop="expiry_date" label="失效日期" width="95" />
        <el-table-column prop="quantity" label="入库数量" width="75" />
        <el-table-column prop="storage_location" label="存放位置" width="90" />
        <el-table-column prop="operator" label="经办人" width="70" />
        <el-table-column prop="inbound_time" label="入库时间" width="150" />
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="printRecord(row)">打印</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <el-dialog v-model="dialogVisible" title="新增入库" width="580px" destroy-on-close>
        <el-form :model="form" label-width="100px" size="default">
          <el-form-item label="耗材" required>
            <el-select v-model="form.consumable_id" filterable placeholder="选择耗材" style="width:100%">
              <el-option v-for="c in consumableList" :key="c.id" :label="c.code + ' ' + c.name + (c.specification?' ('+c.specification+')':'')" :value="c.id" />
            </el-select>
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="批号"><el-input v-model="form.batch_number" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="入库数量" required><el-input-number v-model="form.quantity" :min="1" style="width:100%" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="生产日期"><el-date-picker v-model="form.production_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="失效日期"><el-date-picker v-model="form.expiry_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="存放位置"><el-input v-model="form.storage_location" placeholder="如：A区1号架" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="经办人"><el-input v-model="form.operator" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="入库时间"><el-date-picker v-model="form.inbound_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible=false">取消</el-button>
          <el-button type="primary" @click="saveForm">确认入库</el-button>
        </template>
      </el-dialog>
    </div>
  `
};

// ======================== 出库管理 ========================
const OutboundPage = {
  data() {
    return {
      items: [], total: 0, page: 1, pageSize: 20, keyword: '',
      startDate: '', endDate: '',
      dialogVisible: false, form: {}, outboundItems: [], consumableList: [], deptList: [], batchMap: {},
    };
  },
  async mounted() { this.loadData(); this.loadConsumables(); this.loadDepts(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword });
      if (this.startDate) params.set('start_date', this.startDate);
      if (this.endDate) params.set('end_date', this.endDate);
      const res = await fetch(`${API.outbound}?${params}`);
      const data = await res.json(); this.items = data.items; this.total = data.total;
    },
    async loadConsumables() {
      const res = await fetch(API.consumableAll); this.consumableList = await res.json();
    },
    async loadDepts() {
      const res = await fetch(API.departments); this.deptList = await res.json();
    },
    onSearch() { this.page = 1; this.loadData(); },
    onPageChange(p) { this.page = p; this.loadData(); },
    openAdd() {
      const now = new Date().toISOString().slice(0, 16);
      this.form = { recipient: '', department: '', operator: '', outbound_time: now, remark: '' };
      this.outboundItems = [{ consumable_id: null, quantity: 1, batch_number: '' }];
      this.batchMap = {};
      this.dialogVisible = true;
    },
    addOutboundItem() {
      this.outboundItems.push({ consumable_id: null, quantity: 1, batch_number: '' });
    },
    removeOutboundItem(index) {
      if (this.outboundItems.length > 1) {
        this.outboundItems.splice(index, 1);
      }
    },
    async onConsumableChange(row) {
      row.batch_number = '';
      const cid = row.consumable_id;
      if (!cid) return;
      if (!this.batchMap[cid]) {
        const res = await fetch(`${API.batches}?consumable_id=${cid}`);
        const data = await res.json();
        this.batchMap[cid] = data.items || [];
      }
    },
    getBatchOptions(consumableId) {
      return consumableId ? (this.batchMap[consumableId] || []) : [];
    },
    async saveForm() {
      // 验证：至少有一个明细，且每个明细都有耗材和数量
      const validItems = this.outboundItems.filter(item => item.consumable_id && item.quantity > 0);
      if (validItems.length === 0) { ElMessage.warning('请至少添加一个耗材并填写数量'); return; }
      if (!this.form.operator) { ElMessage.warning('请填写经办人'); return; }

      const payload = {
        items: validItems,
        recipient: this.form.recipient,
        department: this.form.department,
        operator: this.form.operator,
        outbound_time: this.form.outbound_time,
        remark: this.form.remark,
      };
      const res = await fetch(API.outbound, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      if (res.ok) {
        const result = await res.json();
        ElMessage.success(`出库提交成功，共 ${result.count} 条记录`);
        this.dialogVisible = false;
        this.loadData();
      } else {
        const err = await res.json();
        ElMessage.error(err.error || '出库失败');
      }
    },
    async del(row) {
      try { await ElMessageBox.confirm('确定删除该记录？库存将同步恢复', '提示', {type:'warning'}); } catch { return; }
      const res = await fetch(API.outboundDel(row.id), {method:'DELETE'});
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error); }
    },
    formatBatchNumbers(bn, detail) {
      if (!bn) return '';
      // 优先使用 batch_detail 展示每个批号及扣减数量
      if (detail && Array.isArray(detail) && detail.length > 0) {
        return detail.map(d => `<div style="line-height:1.6">${d.batch_number}(${d.quantity})</div>`).join('');
      }
      // 兼容旧数据：仅逗号分隔批号
      const parts = bn.split(',').filter(s => s.trim());
      if (parts.length <= 1) return bn;
      return parts.map(b => `<div style="line-height:1.6">${b}</div>`).join('');
    },
    formatBatchNumberForPrint(item) {
      // 打印模板中批号展示（纯文本，用<br/>换行）
      const detail = item.batch_detail;
      const bn = item.batch_number || '';
      if (detail && Array.isArray(detail) && detail.length > 0) {
        return detail.map(d => `${d.batch_number}(${d.quantity})`).join('<br/>');
      }
      return bn.replace(/,/g, '<br/>');
    },
    gotoExcel() { this.$router.push('/excel'); },
    async printRecord(row) {
      // 打印时需要获取同一单号下的所有明细
      try {
        const res = await fetch(API.outbound + '?document_number=' + encodeURIComponent(row.document_number) + '&page_size=999');
        const data = await res.json();
        const items = data.items || [];
        const rows = items.map(item => `
          <tr>
            <td>${item.consumable_code || ''}</td><td>${item.consumable_name || ''}</td>
            <td>${item.consumable_spec || ''}</td><td>${item.consumable_brand || ''}</td>
            <td>${item.consumable_unit || ''}</td><td>${this.formatBatchNumberForPrint(item)}</td>
            <td>${item.quantity}</td><td>${item.remark || ''}</td>
          </tr>`).join('');
        const html = `
          <h2>出库单</h2>
          <div class="print-info"><span>出库单号：${row.document_number || '-'}</span><span>出库时间：${row.outbound_time || '-'}</span></div>
          <div class="print-info"><span>领用科室：${row.department || '-'}</span><span>领用人：${row.recipient || '-'}</span></div>
          <div class="print-info"><span>经办人：${row.operator || '-'}</span></div>
          <div style="clear:both"></div>
          <table>
            <tr><th>耗材编号</th><th>耗材名称</th><th>规格型号</th><th>品牌</th><th>单位</th><th>批号</th><th>数量</th><th>备注</th></tr>
            ${rows}
          </table>
          <div class="print-footer"><span>领用人签字：__________</span><span>经办人签字：__________</span><span>日期：__________</span></div>`;
        printDocument('出库单 - ' + (row.document_number || ''), html);
      } catch(e) { ElMessage.error('获取打印数据失败'); }
    },
  },
  template: `
    <div>
      <h3 class="page-title">出库管理</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="5"><el-input v-model="keyword" placeholder="单号/编号/名称/科室搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="3"><el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width:100%" /></el-col>
          <el-col :span="3"><el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width:100%" /></el-col>
          <el-col :span="8">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button type="success" @click="openAdd">新增出库</el-button>
            <el-button @click="gotoExcel">Excel导入</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="document_number" label="出库单号" width="150" />
        <el-table-column prop="consumable_code" label="耗材编号" width="120" />
        <el-table-column prop="consumable_name" label="耗材名称" min-width="130" />
        <el-table-column prop="consumable_spec" label="规格型号" width="110" />
        <el-table-column label="批号" width="150">
          <template #default="{row}">
            <span v-html="formatBatchNumbers(row.batch_number, row.batch_detail)"></span>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="出库数量" width="75" />
        <el-table-column prop="recipient" label="领用人" width="70" />
        <el-table-column prop="department" label="领用科室" width="90" />
        <el-table-column prop="operator" label="经办人" width="70" />
        <el-table-column prop="outbound_time" label="出库时间" width="150" />
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="printRecord(row)">打印</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <el-dialog v-model="dialogVisible" title="新增出库" width="700px" destroy-on-close>
        <el-form :model="form" label-width="100px" size="default">
          <el-divider content-position="left">出库明细（可多行）</el-divider>
          <el-table :data="outboundItems" border size="small" style="margin-bottom:12px">
            <el-table-column label="耗材" min-width="180">
              <template #default="{row,$index}">
                <el-select v-model="row.consumable_id" filterable placeholder="选择耗材" style="width:100%" @change="onConsumableChange(row)">
                  <el-option v-for="c in consumableList" :key="c.id" :label="c.code + ' ' + c.name + (c.specification?' ('+c.specification+')':'')" :value="c.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="批号(可选)" width="180">
              <template #default="{row}">
                <el-select v-model="row.batch_number" placeholder="自动(FIFO)" size="small" clearable style="width:100%">
                  <el-option label="自动(FIFO)" value="" />
                  <el-option v-for="b in getBatchOptions(row.consumable_id)" :key="b.batch_number" :label="b.batch_number + ' (库存:' + b.quantity + ')'" :value="b.batch_number" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="数量" width="100">
              <template #default="{row}">
                <el-input-number v-model="row.quantity" :min="1" size="small" style="width:100%" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="60" align="center">
              <template #default="{$index}">
                <el-button link type="danger" size="small" @click="removeOutboundItem($index)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button size="small" @click="addOutboundItem" style="margin-bottom:12px">+ 添加耗材</el-button>
          <el-divider content-position="left">出库信息</el-divider>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="领用人"><el-input v-model="form.recipient" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="领用科室">
              <el-select v-model="form.department" filterable allow-create placeholder="选择或输入科室" style="width:100%">
                <el-option v-for="d in deptList" :key="d.id" :label="d.name" :value="d.name" />
              </el-select>
            </el-form-item></el-col>
          </el-row>
          <el-form-item label="经办人" required><el-input v-model="form.operator" /></el-form-item>
          <el-form-item label="出库时间"><el-date-picker v-model="form.outbound_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible=false">取消</el-button>
          <el-button type="primary" @click="saveForm">确认出库</el-button>
        </template>
      </el-dialog>
    </div>
  `
};

// ======================== 类别管理 ========================
const CategoryPage = {
  data() {
    return {
      items: [],
      dialogVisible: false,
      dialogTitle: '新增类别',
      form: {},
      isEdit: false,
    };
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const res = await fetch(API.categories);
      this.items = await res.json();
    },
    openAdd() {
      this.isEdit = false; this.dialogTitle = '新增类别';
      this.form = { name: '', sort_order: 0 };
      this.dialogVisible = true;
    },
    openEdit(row) {
      this.isEdit = true; this.dialogTitle = '编辑类别';
      this.form = { ...row };
      this.dialogVisible = true;
    },
    async saveForm() {
      if (!this.form.name) { ElMessage.warning('类别名称为必填'); return; }
      const url = this.isEdit ? API.category(this.form.id) : API.categories;
      const method = this.isEdit ? 'PUT' : 'POST';
      const res = await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(this.form) });
      if (res.ok) {
        ElMessage.success(this.isEdit ? '类别更新成功' : '类别新增成功');
        this.dialogVisible = false;
        this.loadData();
        loadCategoryOptions(); // 刷新全局类别列表
      } else {
        const err = await res.json();
        ElMessage.error(err.error || '保存失败');
      }
    },
    async del(row) {
      try { await ElMessageBox.confirm(`确定删除类别 "${row.name}" 吗？`, '提示', { type: 'warning' }); } catch { return; }
      const res = await fetch(API.category(row.id), { method: 'DELETE' });
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); loadCategoryOptions(); }
      else { const err = await res.json(); ElMessage.error(err.error || '删除失败'); }
    },
  },
  template: `
    <div>
      <h3 class="page-title">类别管理</h3>
      <div class="search-bar">
        <el-button type="success" @click="openAdd">新增类别</el-button>
      </div>
      <el-table :data="items" border stripe size="small" style="width:500px">
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column prop="name" label="类别名称" min-width="200" />
        <el-table-column label="操作" width="150">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-dialog v-model="dialogVisible" :title="dialogTitle" width="400px" destroy-on-close>
        <el-form :model="form" label-width="100px" size="default">
          <el-form-item label="类别名称" required><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="排序序号"><el-input-number v-model="form.sort_order" :min="0" style="width:100%" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible=false">取消</el-button>
          <el-button type="primary" @click="saveForm">保存</el-button>
        </template>
      </el-dialog>
    </div>
  `
};

// ======================== 人员管理 ========================
const StaffPage = {
  data() {
    return {
      items: [],
      deptFilter: '',
      dialogVisible: false,
      dialogTitle: '新增人员',
      form: {},
      isEdit: false,
      deptOptions: [],
    };
  },
  async created() {
    await _deptLoaded;
    this.deptOptions = deptOptions;
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams();
      if (this.deptFilter) params.set('department_id', this.deptFilter);
      const res = await fetch(`${API.staff}?${params}`);
      this.items = await res.json();
    },
    onFilterChange() { this.loadData(); },
    openAdd() {
      this.isEdit = false; this.dialogTitle = '新增人员';
      this.form = { name: '', department_id: null, role: '', sort_order: 0 };
      this.deptOptions = deptOptions;
      this.dialogVisible = true;
    },
    openEdit(row) {
      this.isEdit = true; this.dialogTitle = '编辑人员';
      this.form = { ...row };
      this.deptOptions = deptOptions;
      this.dialogVisible = true;
    },
    async saveForm() {
      if (!this.form.name) { ElMessage.warning('姓名为必填'); return; }
      const url = this.isEdit ? API.staffItem(this.form.id) : API.staff;
      const method = this.isEdit ? 'PUT' : 'POST';
      const res = await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(this.form) });
      if (res.ok) {
        ElMessage.success(this.isEdit ? '人员更新成功' : '人员新增成功');
        this.dialogVisible = false;
        this.loadData();
      } else {
        const err = await res.json();
        ElMessage.error(err.error || '保存失败');
      }
    },
    async del(row) {
      try { await ElMessageBox.confirm(`确定删除人员 "${row.name}" 吗？`, '提示', { type: 'warning' }); } catch { return; }
      const res = await fetch(API.staffItem(row.id), { method: 'DELETE' });
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error || '删除失败'); }
    },
    getDeptName(id) {
      const d = this.deptOptions.find(d => d.id === id);
      return d ? d.name : '-';
    },
  },
  template: `
    <div>
      <h3 class="page-title">人员管理</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="5">
            <el-select v-model="deptFilter" placeholder="按科室筛选" clearable @change="onFilterChange" style="width:100%">
              <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-button type="success" @click="openAdd">新增人员</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small" style="width:600px">
        <el-table-column prop="sort_order" label="排序" width="70" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column label="所属科室" width="150">
          <template #default="{row}">{{ getDeptName(row.department_id) }}</template>
        </el-table-column>
        <el-table-column prop="role" label="角色/职务" width="120" />
        <el-table-column label="操作" width="150">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-dialog v-model="dialogVisible" :title="dialogTitle" width="450px" destroy-on-close>
        <el-form :model="form" label-width="100px" size="default">
          <el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="所属科室">
            <el-select v-model="form.department_id" placeholder="选择科室" clearable style="width:100%">
              <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="角色/职务"><el-input v-model="form.role" placeholder="如：护士长、护士" /></el-form-item>
          <el-form-item label="排序序号"><el-input-number v-model="form.sort_order" :min="0" style="width:100%" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible=false">取消</el-button>
          <el-button type="primary" @click="saveForm">保存</el-button>
        </template>
      </el-dialog>
    </div>
  `
};

// ======================== 科室管理 ========================
const DepartmentPage = {
  data() {
    return {
      items: [],
      dialogVisible: false,
      dialogTitle: '新增科室',
      form: {},
      isEdit: false,
    };
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const res = await fetch(API.departments);
      this.items = await res.json();
    },
    openAdd() {
      this.isEdit = false; this.dialogTitle = '新增科室';
      this.form = { name: '', sort_order: 0 };
      this.dialogVisible = true;
    },
    openEdit(row) {
      this.isEdit = true; this.dialogTitle = '编辑科室';
      this.form = { ...row };
      this.dialogVisible = true;
    },
    async saveForm() {
      if (!this.form.name) { ElMessage.warning('科室名称为必填'); return; }
      const url = this.isEdit ? API.department(this.form.id) : API.departments;
      const method = this.isEdit ? 'PUT' : 'POST';
      const res = await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(this.form) });
      if (res.ok) {
        ElMessage.success(this.isEdit ? '科室更新成功' : '科室新增成功');
        this.dialogVisible = false;
        this.loadData();
        loadDeptOptions(); // 刷新全局科室列表
      } else {
        const err = await res.json();
        ElMessage.error(err.error || '保存失败');
      }
    },
    async del(row) {
      try { await ElMessageBox.confirm(`确定删除科室 "${row.name}" 吗？`, '提示', { type: 'warning' }); } catch { return; }
      const res = await fetch(API.department(row.id), { method: 'DELETE' });
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); loadDeptOptions(); }
      else { const err = await res.json(); ElMessage.error(err.error || '删除失败'); }
    },
  },
  template: `
    <div>
      <h3 class="page-title">科室管理</h3>
      <div class="search-bar">
        <el-button type="success" @click="openAdd">新增科室</el-button>
      </div>
      <el-table :data="items" border stripe size="small" style="width:500px">
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column prop="name" label="科室名称" min-width="200" />
        <el-table-column label="操作" width="150">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-dialog v-model="dialogVisible" :title="dialogTitle" width="400px" destroy-on-close>
        <el-form :model="form" label-width="100px" size="default">
          <el-form-item label="科室名称" required><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="排序序号"><el-input-number v-model="form.sort_order" :min="0" style="width:100%" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible=false">取消</el-button>
          <el-button type="primary" @click="saveForm">保存</el-button>
        </template>
      </el-dialog>
    </div>
  `
};

// ======================== 库存查询 ========================
const InventoryPage = {
  data() {
    return {
      items: [], total: 0, page: 1, pageSize: 50, keyword: '', statusFilter: '', categoryFilter: '',
      batchDialogVisible: false, batchItems: [], selectedConsumable: '',
      // 期间库存查询
      periodVisible: false, periodItems: [], periodStart: '', periodEnd: '', periodKeyword: '', periodCategory: '',
      categoryOptions: [],
    };
  },
  async created() {
    await _categoryLoaded;
    this.categoryOptions = categoryOptions;
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword, status: this.statusFilter });
      if (this.categoryFilter) params.set('category', this.categoryFilter);
      const res = await fetch(`${API.inventory}?${params}`);
      const data = await res.json(); this.items = data.items; this.total = data.total;
    },
    onSearch() { this.page = 1; this.loadData(); },
    onPageChange(p) { this.page = p; this.loadData(); },
    stockTagType(s) { return s==='库存不足'?'danger': s==='库存预警'?'warning':'success'; },
    expiryTagType(s) { return s==='已过期'?'danger': s==='近效期'?'warning':'success'; },
    downloadExport(key) { downloadUrl(API[key]); },
    async showBatches(row) {
      this.selectedConsumable = row.name + ' (' + row.code + ')';
      const params = new URLSearchParams({ consumable_id: row.id });
      const res = await fetch(`${API.batches}?${params}`);
      const data = await res.json(); this.batchItems = data.items;
      this.batchDialogVisible = true;
    },
    openPeriodQuery() { this.categoryOptions = categoryOptions; this.periodVisible = true; },
    async queryPeriod() {
      if (!this.periodStart || !this.periodEnd) { ElMessage.warning('请选择开始和结束日期'); return; }
      const params = new URLSearchParams({ start_date: this.periodStart, end_date: this.periodEnd });
      if (this.periodKeyword) params.set('keyword', this.periodKeyword);
      if (this.periodCategory) params.set('category', this.periodCategory);
      const res = await fetch(`${API.periodInventory}?${params}`);
      const data = await res.json();
      this.periodItems = data.items;
    },
  },
  template: `
    <div>
      <h3 class="page-title">库存查询</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="4"><el-input v-model="keyword" placeholder="编号/名称搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="4">
            <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="onSearch" style="width:100%">
              <el-option label="全部" value="all" /><el-option label="库存正常" value="normal" />
              <el-option label="库存不足/预警" value="low_or_warning" />
              <el-option label="近效期" value="expiry_warning" /><el-option label="已过期" value="expired" />
            </el-select>
          </el-col>
          <el-col :span="3">
            <el-select v-model="categoryFilter" placeholder="类别筛选" clearable @change="onSearch" style="width:100%">
              <el-option v-for="c in categoryOptions" :key="c.id" :label="c.name" :value="c.name" />
            </el-select>
          </el-col>
          <el-col :span="8">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button @click="downloadExport('exportInventory')">导出Excel</el-button>
            <el-button type="warning" @click="openPeriodQuery">期间库存查询</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="code" label="耗材编号" width="120" fixed />
        <el-table-column prop="name" label="耗材名称" min-width="130" />
        <el-table-column prop="category" label="类别" width="80" />
        <el-table-column prop="specification" label="规格型号" width="110" />
        <el-table-column prop="total_inbound" label="入库数量" width="75" />
        <el-table-column prop="total_outbound" label="出库数量" width="75" />
        <el-table-column prop="total_stock" label="当前库存" width="75" />
        <el-table-column prop="stock_warning_value" label="预警值" width="60" />
        <el-table-column label="库存状态" width="80">
          <template #default="{row}"><el-tag :type="stockTagType(row.stock_status)" size="small">{{ row.stock_status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="效期状态" width="80">
          <template #default="{row}"><el-tag :type="expiryTagType(row.expiry_status)" size="small">{{ row.expiry_status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{row}"><el-button link type="primary" size="small" @click="showBatches(row)">批次明细</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <!-- 批次明细 -->
      <el-dialog v-model="batchDialogVisible" :title="'批次明细 - ' + selectedConsumable" width="750px" destroy-on-close>
        <el-table :data="batchItems" border stripe size="small">
          <el-table-column prop="batch_number" label="批号" width="130" />
          <el-table-column prop="production_date" label="生产日期" width="100" />
          <el-table-column prop="expiry_date" label="失效日期" width="100" />
          <el-table-column prop="quantity" label="库存数量" width="80" />
          <el-table-column prop="storage_location" label="存放位置" width="100" />
          <el-table-column prop="remark" label="备注" min-width="100" />
        </el-table>
      </el-dialog>
      <!-- 期间库存查询 -->
      <el-dialog v-model="periodVisible" title="期间库存查询" width="900px" destroy-on-close>
        <div class="search-bar">
          <el-row :gutter="12">
            <el-col :span="5"><el-date-picker v-model="periodStart" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width:100%" /></el-col>
            <el-col :span="5"><el-date-picker v-model="periodEnd" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width:100%" /></el-col>
            <el-col :span="4"><el-input v-model="periodKeyword" placeholder="编号/名称" clearable /></el-col>
            <el-col :span="3">
              <el-select v-model="periodCategory" placeholder="类别" clearable style="width:100%">
                <el-option v-for="c in categoryOptions" :key="c.id" :label="c.name" :value="c.name" />
              </el-select>
            </el-col>
            <el-col :span="3"><el-button type="primary" @click="queryPeriod">查询</el-button></el-col>
          </el-row>
        </div>
        <el-table :data="periodItems" border stripe size="small" max-height="400">
          <el-table-column prop="code" label="编号" width="120" />
          <el-table-column prop="name" label="名称" min-width="130" />
          <el-table-column prop="category" label="类别" width="80" />
          <el-table-column prop="initial_stock" label="期初库存" width="80" />
          <el-table-column prop="period_inbound" label="期间入库" width="80" />
          <el-table-column prop="period_outbound" label="期间出库" width="80" />
          <el-table-column prop="ending_stock" label="期末库存" width="80" />
          <el-table-column prop="current_stock" label="当前库存" width="80" />
        </el-table>
      </el-dialog>
    </div>
  `
};

// ======================== 效期查询 ========================
const ExpiryQueryPage = {
  data() {
    return {
      items: [], total: 0, page: 1, pageSize: 50,
      keyword: '', statusFilter: '', categoryFilter: '',
      categoryOptions: [],
    };
  },
  async created() {
    await _categoryLoaded;
    this.categoryOptions = categoryOptions;
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize });
      if (this.keyword) params.set('keyword', this.keyword);
      if (this.statusFilter) params.set('status', this.statusFilter);
      if (this.categoryFilter) params.set('category', this.categoryFilter);
      const res = await fetch(`${API.expiryQuery}?${params}`);
      const data = await res.json(); this.items = data.items; this.total = data.total;
    },
    onSearch() { this.page = 1; this.loadData(); },
    onPageChange(p) { this.page = p; this.loadData(); },
    expiryTagType(s) { return s==='已过期'?'danger': s==='近效期'?'warning':'success'; },
    downloadExport() {
      const params = new URLSearchParams();
      if (this.keyword) params.set('keyword', this.keyword);
      if (this.statusFilter) params.set('status', this.statusFilter);
      if (this.categoryFilter) params.set('category', this.categoryFilter);
      const qs = params.toString();
      const url = qs ? `${API.exportExpiryQuery}?${qs}` : API.exportExpiryQuery;
      downloadUrl(url);
    },
  },
  template: `
    <div>
      <h3 class="page-title">效期查询</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="4"><el-input v-model="keyword" placeholder="编号/名称搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="4">
            <el-select v-model="statusFilter" placeholder="效期状态" clearable @change="onSearch" style="width:100%">
              <el-option label="近效期" value="near_expiry" />
              <el-option label="已过期" value="expired" />
            </el-select>
          </el-col>
          <el-col :span="3">
            <el-select v-model="categoryFilter" placeholder="类别筛选" clearable @change="onSearch" style="width:100%">
              <el-option v-for="c in categoryOptions" :key="c.id" :label="c.name" :value="c.name" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button @click="downloadExport">导出Excel</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="code" label="编号" width="120" fixed />
        <el-table-column prop="name" label="名称" min-width="130" />
        <el-table-column prop="category" label="类别" width="80" />
        <el-table-column prop="batch_number" label="批次" width="140" />
        <el-table-column prop="storage_location" label="存放位置" width="100" />
        <el-table-column prop="production_date" label="生产日期" width="100" />
        <el-table-column prop="expiry_date" label="失效日期" width="100" />
        <el-table-column label="效期状态" width="80">
          <template #default="{row}"><el-tag :type="expiryTagType(row.expiry_status)" size="small">{{ row.expiry_status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="quantity" label="当前库存" width="80" />
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
    </div>
  `
};

// ======================== 库存盘点 ========================
const InventoryCheckPage = {
  data() {
    return {
      items: [],
      detailVisible: false, detailData: null,
      createVisible: false, createForm: { check_date: '', remark: '' },
    };
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const res = await fetch(API.inventoryChecks);
      this.items = await res.json();
    },
    openCreate() {
      this.createForm = { check_date: new Date().toISOString().slice(0,10), remark: '' };
      this.createVisible = true;
    },
    async saveCreate() {
      const res = await fetch(API.inventoryChecks, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(this.createForm) });
      if (res.ok) {
        ElMessage.success('盘点单创建成功');
        this.createVisible = false;
        this.loadData();
      } else {
        const err = await res.json(); ElMessage.error(err.error || '创建失败');
      }
    },
    async viewDetail(row) {
      const res = await fetch(API.inventoryCheck(row.id));
      this.detailData = await res.json();
      this.detailVisible = true;
    },
    async saveDetail() {
      if (!this.detailData) return;
      const items = this.detailData.items.map(i => ({
        id: i.id, actual_quantity: i.actual_quantity, remark: i.remark
      }));
      const res = await fetch(API.inventoryCheck(this.detailData.id), {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ items })
      });
      if (res.ok) {
        this.detailData = await res.json();
        ElMessage.success('保存成功');
      } else {
        const err = await res.json(); ElMessage.error(err.error || '保存失败');
      }
    },
    async confirmCheck(row) {
      try {
        await ElMessageBox.confirm(
          '确认盘点后系统将自动调整库存（盘盈补入、盘亏扣减），此操作不可撤销。确定确认？',
          '确认盘点', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
        );
      } catch { return; }
      const res = await fetch(API.inventoryCheckConfirm(row.id), { method: 'POST' });
      if (res.ok) {
        ElMessage.success('盘点确认成功，库存已调整');
        this.loadData();
        if (this.detailVisible && this.detailData && this.detailData.id === row.id) {
          this.detailData = await (await fetch(API.inventoryCheck(row.id))).json();
        }
      } else {
        const err = await res.json(); ElMessage.error(err.error || '确认失败');
      }
    },
    async del(row) {
      try { await ElMessageBox.confirm('确定删除该盘点单？', '提示', { type: 'warning' }); } catch { return; }
      const res = await fetch(API.inventoryCheck(row.id), { method: 'DELETE' });
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error); }
    },
    statusTag(s) { return s === 'draft' ? 'info' : 'success'; },
    statusText(s) { return s === 'draft' ? '草稿' : '已确认'; },
    diffTagType(d) { return d > 0 ? 'success' : d < 0 ? 'danger' : 'info'; },
  },
  template: `
    <div>
      <h3 class="page-title">库存盘点</h3>
      <div class="search-bar">
        <el-button type="success" @click="openCreate">新建盘点</el-button>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="id" label="盘点单号" width="100" />
        <el-table-column prop="check_date" label="盘点日期" width="120" />
        <el-table-column label="状态" width="90">
          <template #default="{row}"><el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="200" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="viewDetail(row)">明细</el-button>
            <el-button v-if="row.status==='draft'" link type="success" size="small" @click="confirmCheck(row)">确认</el-button>
            <el-button v-if="row.status==='draft'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <!-- 新建盘点 -->
      <el-dialog v-model="createVisible" title="新建盘点" width="400px" destroy-on-close>
        <el-form :model="createForm" label-width="100px">
          <el-form-item label="盘点日期"><el-date-picker v-model="createForm.check_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="createForm.remark" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="createVisible=false">取消</el-button>
          <el-button type="primary" @click="saveCreate">创建</el-button>
        </template>
      </el-dialog>
      <!-- 盘点明细 -->
      <el-dialog v-model="detailVisible" :title="'盘点明细 - 单号' + (detailData?detailData.id:'')" width="950px" destroy-on-close>
        <div v-if="detailData" style="margin-bottom:12px">
          <span>盘点日期：{{ detailData.check_date }}</span>&nbsp;&nbsp;
          <el-tag :type="statusTag(detailData.status)" size="small">{{ statusText(detailData.status) }}</el-tag>&nbsp;&nbsp;
          <span>备注：{{ detailData.remark || '-' }}</span>
        </div>
        <el-table :data="detailData?detailData.items:[]" border stripe size="small" max-height="450">
          <el-table-column prop="consumable_code" label="编号" width="120" />
          <el-table-column prop="consumable_name" label="名称" min-width="140" />
          <el-table-column prop="consumable_spec" label="规格" width="100" />
          <el-table-column prop="system_quantity" label="系统库存" width="80" />
          <el-table-column label="实盘数量" width="120">
            <template #default="{row}">
              <el-input-number v-if="detailData.status==='draft'" v-model="row.actual_quantity" :min="0" size="small" style="width:100%"
                @change="row.difference = (row.actual_quantity||0) - row.system_quantity" />
              <span v-else>{{ row.actual_quantity }}</span>
            </template>
          </el-table-column>
          <el-table-column label="差异" width="80">
            <template #default="{row}">
              <el-tag :type="diffTagType(row.difference)" size="small">{{ row.difference > 0 ? '+' : '' }}{{ row.difference }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="备注" width="150">
            <template #default="{row}">
              <el-input v-if="detailData.status==='draft'" v-model="row.remark" size="small" />
              <span v-else>{{ row.remark }}</span>
            </template>
          </el-table-column>
        </el-table>
        <template #footer v-if="detailData && detailData.status==='draft'">
          <el-button @click="detailVisible=false">取消</el-button>
          <el-button type="primary" @click="saveDetail">保存</el-button>
          <el-button type="success" @click="confirmCheck(detailData);detailVisible=false">确认盘点</el-button>
        </template>
        <template #footer v-else>
          <el-button @click="detailVisible=false">关闭</el-button>
        </template>
      </el-dialog>
    </div>
  `
};

// ======================== Excel导入导出 ========================
const ExcelPage = {
  data() {
    return {
      importMode: 'skip', importResult: null, importLoading: false,
    };
  },
  methods: {
    downloadExport(key) { downloadUrl(API[key]); },
    downloadTemplate(key) { downloadUrl(API[key]); },
    async handleImportConsumable(file) {
      this.importLoading = true; this.importResult = null;
      const fd = new FormData();
      fd.append('file', file.raw);
      fd.append('mode', this.importMode);
      try {
        const res = await fetch(API.importConsumable, { method: 'POST', body: fd });
        this.importResult = await res.json();
        if (this.importResult.success > 0 || this.importResult.updated > 0) ElMessage.success(`导入完成: 新增${this.importResult.success}条, 更新${this.importResult.updated}条, 跳过${this.importResult.skipped}条`);
        else if (this.importResult.errors?.length) ElMessage.error('导入有错误，请查看详情');
      } catch(e) { ElMessage.error('导入失败: ' + e.message); }
      this.importLoading = false;
    },
    async handleImportInbound(file) {
      this.importLoading = true; this.importResult = null;
      const fd = new FormData(); fd.append('file', file.raw);
      try {
        const res = await fetch(API.importInbound, { method: 'POST', body: fd });
        this.importResult = await res.json();
        if (this.importResult.success > 0) ElMessage.success(`入库导入完成: 成功${this.importResult.success}条`);
      } catch(e) { ElMessage.error('导入失败'); }
      this.importLoading = false;
    },
    async handleImportOutbound(file) {
      this.importLoading = true; this.importResult = null;
      const fd = new FormData(); fd.append('file', file.raw);
      try {
        const res = await fetch(API.importOutbound, { method: 'POST', body: fd });
        this.importResult = await res.json();
        if (this.importResult.success > 0) ElMessage.success(`出库导入完成: 成功${this.importResult.success}条`);
      } catch(e) { ElMessage.error('导入失败'); }
      this.importLoading = false;
    },
  },
  template: `
    <div>
      <h3 class="page-title">Excel导入导出</h3>
      <el-row :gutter="20">
        <el-col :span="14">
          <el-card shadow="hover">
            <template #header><span>数据导入</span></template>
            <div class="import-section">
              <div class="import-section-title">耗材基础信息</div>
              <el-radio-group v-model="importMode" style="margin-bottom:12px">
                <el-radio value="skip">跳过已有编号</el-radio>
                <el-radio value="update">更新已有编号</el-radio>
              </el-radio-group>
              <div v-if="importMode==='update'" style="margin-bottom:8px;color:#909399;font-size:12px">更新模式：按编号匹配已有耗材，留空字段不修改</div>
              <el-upload :auto-upload="false" accept=".xlsx,.xls" :show-file-list="false" :on-change="handleImportConsumable" :disabled="importLoading">
                <el-button type="primary" :loading="importLoading">选择Excel文件</el-button>
              </el-upload>
              <div style="margin-top:8px"><el-button link type="info" @click="downloadTemplate('tplConsumable')">下载模板</el-button></div>
            </div>
            <el-divider />
            <div class="import-section">
              <div class="import-section-title">入库记录</div>
              <el-upload :auto-upload="false" accept=".xlsx,.xls" :show-file-list="false" :on-change="handleImportInbound" :disabled="importLoading">
                <el-button type="primary" :loading="importLoading">选择Excel文件</el-button>
              </el-upload>
              <div style="margin-top:8px"><el-button link type="info" @click="downloadTemplate('tplInbound')">下载模板</el-button></div>
            </div>
            <el-divider />
            <div class="import-section">
              <div class="import-section-title">出库记录</div>
              <el-upload :auto-upload="false" accept=".xlsx,.xls" :show-file-list="false" :on-change="handleImportOutbound" :disabled="importLoading">
                <el-button type="primary" :loading="importLoading">选择Excel文件</el-button>
              </el-upload>
              <div style="margin-top:8px"><el-button link type="info" @click="downloadTemplate('tplOutbound')">下载模板</el-button></div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card shadow="hover">
            <template #header><span>数据导出</span></template>
            <div class="export-buttons">
              <el-button type="success" @click="downloadExport('exportConsumable')">导出耗材基础信息</el-button>
              <el-button type="success" @click="downloadExport('exportInventory')">导出库存总览</el-button>
              <el-button type="success" @click="downloadExport('exportInbound')">导出入库记录</el-button>
              <el-button type="success" @click="downloadExport('exportOutbound')">导出出库记录</el-button>
            </div>
          </el-card>
          <el-card v-if="importResult" shadow="hover" style="margin-top:20px">
            <template #header><span>导入结果</span></template>
            <div class="result-info">
              <span style="color:#67C23A">成功: {{ importResult.success || 0 }} 条</span>
              <span v-if="importResult.updated" style="color:#409EFF">更新: {{ importResult.updated }} 条</span>
              <span v-if="importResult.skipped" style="color:#909399">跳过: {{ importResult.skipped }} 条</span>
            </div>
            <div v-if="importResult.errors?.length" class="result-errors">
              <p style="color:#F56C6C;margin:8px 0 4px">错误:</p>
              <ul><li v-for="e in importResult.errors" :key="e">{{ e }}</li></ul>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  `
};

// ======================== Vue App ========================
const app = Vue.createApp({
  data() { return { activeMenu: 'dashboard', locale: window.ElementPlusLocaleZhCn || {} }; },
  methods: {
    handleMenuSelect(key) { this.$router.push({ name: key }); }
  }
});

const router = VueRouter.createRouter({
  history: VueRouter.createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: DashboardPage, name: 'dashboard' },
    { path: '/consumable', component: ConsumablePage, name: 'consumable' },
    { path: '/inbound', component: InboundPage, name: 'inbound' },
    { path: '/outbound', component: OutboundPage, name: 'outbound' },
    { path: '/inventory', component: InventoryPage, name: 'inventory' },
    { path: '/expiry-query', component: ExpiryQueryPage, name: 'expiry-query' },
    { path: '/inventory-check', component: InventoryCheckPage, name: 'inventory-check' },
    { path: '/category', component: CategoryPage, name: 'category' },
    { path: '/staff', component: StaffPage, name: 'staff' },
    { path: '/department', component: DepartmentPage, name: 'department' },
    { path: '/excel', component: ExcelPage, name: 'excel' },
  ]
});

app.use(router);
// 设置 Element Plus 为中文
app.use(ElementPlus, { locale: window.ElementPlusLocaleZhCn });

app.mount('#app');