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
  // 出库
  outbound: '/api/stock/outbound',
  outboundDel: id => `/api/stock/outbound/${id}`,
  // 科室
  departments: '/api/departments',
  department: id => `/api/departments/${id}`,
  departmentsInit: '/api/departments/init',
  // 库存
  inventory: '/api/stock/inventory',
  batches: '/api/stock/batches',
  dashboard: '/api/stock/dashboard',
  // Excel
  tplConsumable: '/api/excel/template/consumable',
  tplInbound: '/api/excel/template/inbound',
  importConsumable: '/api/excel/import/consumable',
  importInbound: '/api/excel/import/inbound',
  exportConsumable: '/api/excel/export/consumable',
  exportInventory: '/api/excel/export/inventory',
  exportInbound: '/api/excel/export/inbound',
  exportOutbound: '/api/excel/export/outbound',
};

// 下载/导出：构建绝对URL后直接让浏览器打开下载
function downloadUrl(path) {
  const baseUrl = window.location.origin;
  const fullUrl = path.startsWith('/') ? baseUrl + path : baseUrl + '/' + path;
  window.location.href = fullUrl;
}

// 科室列表（从后端动态加载）
let deptOptions = [];
async function loadDeptOptions() {
  try {
    const res = await fetch(API.departments);
    const data = await res.json();
    if (Array.isArray(data) && data.length === 0) {
      // 首次使用，初始化默认科室
      await fetch(API.departmentsInit, { method: 'POST' });
      const res2 = await fetch(API.departments);
      data = await res2.json();
    }
    deptOptions = data;
  } catch (e) { console.error('加载科室列表失败', e); }
}
loadDeptOptions();

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
          <div class="stat-value warning-value">{{ stats.warning_count }}</div><div class="stat-label">库存预警</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value danger-value">{{ stats.expired_count }}</div><div class="stat-label">效期预警</div>
        </el-card>
      </div>
      <el-row :gutter="20" v-if="stats">
        <el-col :span="12">
          <el-card shadow="hover" style="margin-bottom:20px">
            <template #header><span>⚠️ 库存预警</span></template>
            <el-table :data="stats.warning_items" size="small" empty-text="暂无预警">
              <el-table-column prop="code" label="编号" width="140" />
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="total_stock" label="当前库存" width="90" />
              <el-table-column prop="stock_warning_value" label="预警值" width="90" />
              <el-table-column prop="status" label="状态" width="90">
                <template #default="{row}">
                  <el-tag :type="row.status==='库存不足'?'danger':'warning'" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover" style="margin-bottom:20px">
            <template #header><span>⏰ 效期预警</span></template>
            <el-table :data="stats.expired_items" size="small" empty-text="暂无预警">
              <el-table-column prop="code" label="编号" width="140" />
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="expiry_status" label="效期状态" width="100">
                <template #default="{row}">
                  <el-tag :type="row.expiry_status==='已过期'?'danger':'warning'" size="small">{{ row.expiry_status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
          <el-card shadow="hover">
            <template #header><span>📊 科室出库统计</span></template>
            <el-table :data="stats.dept_stats" size="small" empty-text="暂无数据">
              <el-table-column prop="department" label="科室" />
              <el-table-column prop="total" label="出库数量" width="100" />
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
      items: [], total: 0, page: 1, pageSize: 20, keyword: '',
      dialogVisible: false, dialogTitle: '新增耗材', form: {}, isEdit: false,
    };
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword, include_stock: 'true' });
      const res = await fetch(`${API.consumables}?${params}`);
      const data = await res.json();
      this.items = data.items; this.total = data.total;
    },
    onSearch() { this.page = 1; this.loadData(); },
    onPageChange(p) { this.page = p; this.loadData(); },
    openAdd() {
      this.isEdit = false; this.dialogTitle = '新增耗材';
      this.form = { code:'', name:'', brand:'', manufacturer:'', specification:'', unit:'', stock_warning_value:0, expiry_warning_days:0, remark:'' };
      this.dialogVisible = true;
    },
    openEdit(row) {
      this.isEdit = true; this.dialogTitle = '编辑耗材'; this.form = { ...row }; this.dialogVisible = true;
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
          <el-col :span="6"><el-input v-model="keyword" placeholder="编号/名称/品牌搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="8">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button type="success" @click="openAdd">新增耗材</el-button>
            <el-button @click="gotoExcel">Excel导入导出</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small" style="width:100%">
        <el-table-column prop="code" label="耗材编号" width="140" fixed />
        <el-table-column prop="name" label="耗材名称" min-width="160" />
        <el-table-column prop="brand" label="品牌" width="100" />
        <el-table-column prop="manufacturer" label="生产厂家" width="120" />
        <el-table-column prop="specification" label="规格型号" width="150" />
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="total_stock" label="库存" width="70" />
        <el-table-column label="库存状态" width="90">
          <template #default="{row}">
            <el-tag v-if="row.stock_status" :type="stockTagType(row.stock_status)" size="small">{{ row.stock_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="效期状态" width="90">
          <template #default="{row}">
            <el-tag v-if="row.expiry_status" :type="expiryTagType(row.expiry_status)" size="small">{{ row.expiry_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="stock_warning_value" label="预警值" width="70" />
        <el-table-column prop="expiry_warning_days" label="效期预警天数" width="100" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" destroy-on-close>
        <el-form :model="form" label-width="120px" size="default">
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="耗材编号" required><el-input v-model="form.code" :disabled="isEdit" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="耗材名称" required><el-input v-model="form.name" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="品牌名称"><el-input v-model="form.brand" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="生产厂家"><el-input v-model="form.manufacturer" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="规格型号"><el-input v-model="form.specification" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="单位"><el-input v-model="form.unit" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="库存预警值"><el-input-number v-model="form.stock_warning_value" :min="0" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="效期预警天数"><el-input-number v-model="form.expiry_warning_days" :min="0" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
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
      dialogVisible: false, form: {}, consumableList: [],
    };
  },
  async mounted() { this.loadData(); this.loadConsumables(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword });
      const res = await fetch(`${API.inbound}?${params}`);
      const data = await res.json(); this.items = data.items; this.total = data.total;
    },
    async loadConsumables() {
      const res = await fetch(API.consumableAll); this.consumableList = await res.json();
    },
    onSearch() { this.page = 1; this.loadData(); },
    onPageChange(p) { this.page = p; this.loadData(); },
    openAdd() {
      this.form = { consumable_id: null, batch_number: '', production_date: '', expiry_date: '', quantity: 1, operator: '', remark: '' };
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
  },
  template: `
    <div>
      <h3 class="page-title">入库管理</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="6"><el-input v-model="keyword" placeholder="编号/名称/批号搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="6">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button type="success" @click="openAdd">新增入库</el-button>
            <el-button @click="gotoExcel">Excel导入</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="consumable_code" label="耗材编号" width="140" />
        <el-table-column prop="consumable_name" label="耗材名称" min-width="140" />
        <el-table-column prop="consumable_spec" label="规格型号" width="130" />
        <el-table-column prop="batch_number" label="批号" width="120" />
        <el-table-column prop="production_date" label="生产日期" width="100" />
        <el-table-column prop="expiry_date" label="失效日期" width="100" />
        <el-table-column prop="quantity" label="入库数量" width="80" />
        <el-table-column prop="operator" label="经办人" width="80" />
        <el-table-column prop="inbound_time" label="入库时间" width="160" />
        <el-table-column prop="remark" label="备注" min-width="100" />
        <el-table-column label="操作" width="70" fixed="right">
          <template #default="{row}"><el-button link type="danger" size="small" @click="del(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <el-dialog v-model="dialogVisible" title="新增入库" width="560px" destroy-on-close>
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
          <el-form-item label="经办人"><el-input v-model="form.operator" /></el-form-item>
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
      dialogVisible: false, form: {}, consumableList: [], deptList: [],
    };
  },
  async mounted() { this.loadData(); this.loadConsumables(); this.loadDepts(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword });
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
      this.form = { consumable_id: null, batch_number: '', quantity: 1, recipient: '', department: '', operator: '', remark: '' };
      this.dialogVisible = true;
    },
    async saveForm() {
      if (!this.form.consumable_id || !this.form.quantity) { ElMessage.warning('请选择耗材并填写数量'); return; }
      const res = await fetch(API.outbound, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(this.form) });
      if (res.ok) { ElMessage.success('出库提交成功'); this.dialogVisible = false; this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error || '出库失败'); }
    },
    async del(row) {
      try { await ElMessageBox.confirm('确定删除该记录？库存将同步恢复', '提示', {type:'warning'}); } catch { return; }
      const res = await fetch(API.outboundDel(row.id), {method:'DELETE'});
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); }
      else { const err = await res.json(); ElMessage.error(err.error); }
    },
  },
  template: `
    <div>
      <h3 class="page-title">出库管理</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="6"><el-input v-model="keyword" placeholder="编号/名称/科室搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="6">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button type="success" @click="openAdd">新增出库</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="consumable_code" label="耗材编号" width="140" />
        <el-table-column prop="consumable_name" label="耗材名称" min-width="140" />
        <el-table-column prop="consumable_spec" label="规格型号" width="130" />
        <el-table-column prop="batch_number" label="批号" width="120" />
        <el-table-column prop="quantity" label="出库数量" width="80" />
        <el-table-column prop="recipient" label="领用人" width="80" />
        <el-table-column prop="department" label="领用科室" width="110" />
        <el-table-column prop="operator" label="经办人" width="80" />
        <el-table-column prop="outbound_time" label="出库时间" width="160" />
        <el-table-column prop="remark" label="备注" min-width="100" />
        <el-table-column label="操作" width="70" fixed="right">
          <template #default="{row}"><el-button link type="danger" size="small" @click="del(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <el-dialog v-model="dialogVisible" title="新增出库" width="560px" destroy-on-close>
        <el-form :model="form" label-width="100px" size="default">
          <el-form-item label="耗材" required>
            <el-select v-model="form.consumable_id" filterable placeholder="选择耗材" style="width:100%">
              <el-option v-for="c in consumableList" :key="c.id" :label="c.code + ' ' + c.name + (c.specification?' ('+c.specification+')':'')" :value="c.id" />
            </el-select>
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="批号(可选)"><el-input v-model="form.batch_number" placeholder="不填则自动先进先出" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="出库数量" required><el-input-number v-model="form.quantity" :min="1" style="width:100%" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="领用人"><el-input v-model="form.recipient" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="领用科室">
              <el-select v-model="form.department" filterable allow-create placeholder="选择或输入科室" style="width:100%">
                <el-option v-for="d in deptList" :key="d.id" :label="d.name" :value="d.name" />
              </el-select>
            </el-form-item></el-col>
          </el-row>
          <el-form-item label="经办人"><el-input v-model="form.operator" /></el-form-item>
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
      } else {
        const err = await res.json();
        ElMessage.error(err.error || '保存失败');
      }
    },
    async del(row) {
      try { await ElMessageBox.confirm(`确定删除科室 "${row.name}" 吗？`, '提示', { type: 'warning' }); } catch { return; }
      const res = await fetch(API.department(row.id), { method: 'DELETE' });
      if (res.ok) { ElMessage.success('删除成功'); this.loadData(); }
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
      items: [], total: 0, page: 1, pageSize: 50, keyword: '', statusFilter: '',
      batchDialogVisible: false, batchItems: [], selectedConsumable: '',
    };
  },
  mounted() { this.loadData(); },
  methods: {
    async loadData() {
      const params = new URLSearchParams({ page: this.page, page_size: this.pageSize, keyword: this.keyword, status: this.statusFilter });
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
  },
  template: `
    <div>
      <h3 class="page-title">库存查询</h3>
      <div class="search-bar">
        <el-row :gutter="12">
          <el-col :span="5"><el-input v-model="keyword" placeholder="编号/名称搜索" clearable @keyup.enter="onSearch" /></el-col>
          <el-col :span="5">
            <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="onSearch" style="width:100%">
              <el-option label="全部" value="all" /><el-option label="库存正常" value="normal" />
              <el-option label="库存预警" value="warning" /><el-option label="库存不足" value="low" />
              <el-option label="近效期" value="expiry_warning" /><el-option label="已过期" value="expired" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-button type="primary" @click="onSearch">搜索</el-button>
            <el-button @click="downloadExport('exportInventory')">导出Excel</el-button>
          </el-col>
        </el-row>
      </div>
      <el-table :data="items" border stripe size="small">
        <el-table-column prop="code" label="耗材编号" width="140" fixed />
        <el-table-column prop="name" label="耗材名称" min-width="140" />
        <el-table-column prop="specification" label="规格型号" width="130" />
        <el-table-column prop="manufacturer" label="生产厂家" width="120" />
        <el-table-column prop="total_inbound" label="入库数量" width="80" />
        <el-table-column prop="total_outbound" label="出库数量" width="80" />
        <el-table-column prop="total_stock" label="当前库存" width="80" />
        <el-table-column prop="stock_warning_value" label="预警值" width="70" />
        <el-table-column label="库存状态" width="90">
          <template #default="{row}"><el-tag :type="stockTagType(row.stock_status)" size="small">{{ row.stock_status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="expiry_warning_days" label="效期预警天数" width="100" />
        <el-table-column label="效期状态" width="90">
          <template #default="{row}"><el-tag :type="expiryTagType(row.expiry_status)" size="small">{{ row.expiry_status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{row}"><el-button link type="primary" size="small" @click="showBatches(row)">批次明细</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="onPageChange" />
      <el-dialog v-model="batchDialogVisible" :title="'批次明细 - ' + selectedConsumable" width="750px" destroy-on-close>
        <el-table :data="batchItems" border stripe size="small">
          <el-table-column prop="batch_number" label="批号" width="130" />
          <el-table-column prop="production_date" label="生产日期" width="100" />
          <el-table-column prop="expiry_date" label="失效日期" width="100" />
          <el-table-column prop="quantity" label="库存数量" width="80" />
          <el-table-column prop="remark" label="备注" min-width="100" />
        </el-table>
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
  },
  template: `
    <div>
      <h3 class="page-title">Excel导入导出</h3>
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="hover" style="margin-bottom:20px">
            <template #header><span>📥 导入耗材基础信息</span></template>
            <el-radio-group v-model="importMode" style="margin-bottom:12px">
              <el-radio value="skip">跳过已有编号</el-radio>
              <el-radio value="update">更新已有编号</el-radio>
            </el-radio-group>
            <el-upload :auto-upload="false" accept=".xlsx,.xls" :show-file-list="false" :on-change="handleImportConsumable" :disabled="importLoading">
              <el-button type="primary" :loading="importLoading">选择Excel文件导入耗材</el-button>
            </el-upload>
            <div style="margin-top:8px"><el-button link type="info" @click="downloadTemplate('tplConsumable')">下载导入模板</el-button></div>
          </el-card>
          <el-card shadow="hover">
            <template #header><span>📥 批量导入入库记录</span></template>
            <el-upload :auto-upload="false" accept=".xlsx,.xls" :show-file-list="false" :on-change="handleImportInbound" :disabled="importLoading">
              <el-button type="primary" :loading="importLoading">选择Excel文件导入入库</el-button>
            </el-upload>
            <div style="margin-top:8px"><el-button link type="info" @click="downloadTemplate('tplInbound')">下载导入模板</el-button></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header><span>📤 导出数据</span></template>
            <div style="display:flex;flex-direction:column;gap:12px">
              <el-button type="success" @click="downloadExport('exportConsumable')">导出耗材基础信息</el-button>
              <el-button type="success" @click="downloadExport('exportInventory')">导出库存总览</el-button>
              <el-button type="success" @click="downloadExport('exportInbound')">导出入库记录</el-button>
              <el-button type="success" @click="downloadExport('exportOutbound')">导出出库记录</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <el-card v-if="importResult" shadow="hover" style="margin-top:20px">
        <template #header><span>📋 导入结果</span></template>
        <p>✅ 新增: {{ importResult.success || 0 }} 条</p>
        <p>🔄 更新: {{ importResult.updated || 0 }} 条</p>
        <p>⏭️ 跳过: {{ importResult.skipped || 0 }} 条</p>
        <div v-if="importResult.errors?.length">
          <p style="color:#F56C6C">⚠️ 错误:</p>
          <ul><li v-for="e in importResult.errors" :key="e" style="color:#F56C6C;font-size:13px">{{ e }}</li></ul>
        </div>
      </el-card>
    </div>
  `
};

// ======================== Vue App ========================
const app = Vue.createApp({
  data() { return { activeMenu: 'dashboard' }; },
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
    { path: '/department', component: DepartmentPage, name: 'department' },
    { path: '/excel', component: ExcelPage, name: 'excel' },
  ]
});

app.use(router);
app.use(ElementPlus);
app.mount('#app');