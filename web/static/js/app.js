// 已迁移为 ESM 入口 bootstrap.js；保留空文件或简短注释以兼容旧引用

// Tab 切换
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      
      // 更新按钮状态
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      // 更新内容显示
      tabContents.forEach(content => {
        if (content.dataset.content === tab) {
          content.classList.add('active');
          
          // 如果切换到手动下载页面，刷新日志
          if (tab === 'manual') {
            loadManualLogs();
          }
        } else {
          content.classList.remove('active');
        }
      });
    });
  });
}

// 下载逻辑已迁移至 download.js

// 导出逻辑已迁移至 export.js

// 加载任务列表
async function loadTasks() {
  try {
    const response = await fetch(`${API_BASE}/api/tasks`);
    const tasks = await response.json();
    
    const taskList = document.getElementById('taskList');
    
    if (tasks.length === 0) {
      taskList.innerHTML = '<div class="empty-state">暂无任务</div>';
      return;
    }
    
    taskList.innerHTML = tasks.map(task => `
      <div class="task-item ${task.status}">
        <div class="task-header">
          <div class="task-meta">
            <span class="status-badge ${task.status}">
              ${task.status === 'running' ? '运行中' : 
                task.status === 'completed' ? '已完成' :
                task.status === 'failed' ? '失败' : '等待中'}
            </span>
            <span>任务 #${task.id}</span>
            <span>${task.type === 'download' ? '📥 下载' : '📦 导出'}</span>
          </div>
          <span class="task-time">${formatTime(task.create_time)}</span>
        </div>
        
        <div class="task-content">
          ${task.type === 'download' ? 
            `本子: ${task.album_ids.length} 个，章节: ${task.photo_ids.length} 个` :
            `账号: ${task.username}`}
          ${task.error ? `\n错误: ${task.error}` : ''}
          ${task.status === 'completed' && task.start_time && task.end_time ? 
            `\n耗时: ${formatDuration(task.start_time, task.end_time)}` : ''}
        </div>
        
        <div class="task-actions">
          ${task.status !== 'running' ? `
            <button class="btn-delete" onclick="deleteTask(${task.id})">删除</button>
          ` : ''}
        </div>
      </div>
    `).join('');
  } catch (error) {
    console.error('加载任务失败:', error);
  }
}

// 删除任务逻辑已迁移至 logs.js

// 手动日志加载与渲染逻辑已迁移至 logs.js

function applyManualFilters() {
  const filterLevel = document.getElementById('manualFilterLevel')?.value || 'all';
  const filterTimeRange = document.getElementById('manualFilterTimeRange')?.value || 'all';
  const filterKeyword = document.getElementById('manualFilterKeyword')?.value.toLowerCase() || '';
  
  let filteredTasks = [...manualTasksCache];
  
  // 按状态筛选（将级别映射到任务状态）
  if (filterLevel !== 'all') {
    const statusMap = {
      'info': 'running',
      'success': 'completed',
      'error': 'failed'
    };
    const targetStatus = statusMap[filterLevel];
    if (targetStatus) {
      filteredTasks = filteredTasks.filter(task => task.status === targetStatus);
    }
  }
  
  // 按时间范围筛选
  if (filterTimeRange !== 'all') {
    const hours = parseInt(filterTimeRange);
    const cutoffTime = Date.now() - (hours * 60 * 60 * 1000);
    filteredTasks = filteredTasks.filter(task => new Date(task.create_time).getTime() > cutoffTime);
  }
  
  // 按关键词筛选（搜索任务相关信息）
  if (filterKeyword) {
    filteredTasks = filteredTasks.filter(task => {
      const searchText = `任务#${task.id} ${task.type} ${task.status} ${task.config?.username || ''}`.toLowerCase();
      return searchText.includes(filterKeyword);
    });
  }
  
  // 显示任务卡片
  const logList = document.getElementById('manualLogsList');
  if (!logList) return;
  
  // 保存当前滚动位置
  const scrollTop = logList.scrollTop;
  
  if (filteredTasks.length === 0) {
    logList.innerHTML = '<div class="empty-state">暂无符合条件的任务</div>';
    return;
  }
  
  // 渲染任务卡片（与任务列表相同的样式）
  logList.innerHTML = filteredTasks.slice(-50).reverse().map(task => {
    const summary = task.type === 'download' ? 
      `${task.album_ids.length}个本子, ${task.photo_ids.length}个章节` :
      `账号: ${task.config?.username || '未知'}`;
    
    // 检查是否已展开
    const isExpanded = manualExpandedTasks.has(task.id);
    
    return `
      <div class="task-item ${task.status}" data-task-id="${task.id}">
        <div class="task-item-header" data-action="toggle" data-task-id="${task.id}">
          <span class="task-expand-icon ${isExpanded ? 'expanded' : ''}" id="log-task-expand-icon-${task.id}">▶</span>
          <span class="task-status-badge ${task.status}">
            ${task.status === 'running' ? '运行中' : 
              task.status === 'completed' ? '已完成' :
              task.status === 'failed' ? '失败' : '等待中'}
          </span>
          <span class="task-id">任务 #${task.id}</span>
          <span class="task-time-compact">${formatTime(task.create_time)}</span>
          <span class="task-summary">${summary}</span>
          <div class="task-actions-compact">
            ${task.status !== 'running' ? `
              <button class="icon-delete-btn" data-action="delete" data-task-id="${task.id}" title="删除">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
              </button>
            ` : ''}
          </div>
        </div>
        
        <div class="task-detail-content ${isExpanded ? 'expanded' : ''}" id="log-task-detail-${task.id}">
          <div class="task-detail-inner">
            <!-- 任务信息 -->
            <div class="task-detail-section">
              <div class="task-detail-title">任务信息</div>
              <div class="task-detail-info task-detail-info-grid">
                <div class="task-detail-info-item">类型: ${task.type === 'download' ? '下载本子' : '导出收藏夹'}</div>
                ${task.type === 'download' ? `
                  <div class="task-detail-info-item">本子数: ${task.album_ids.length}，章节数: ${task.photo_ids.length}</div>
                  ${task.album_ids.length > 0 && task.album_ids.length <= 5 ? `
                    <div class="task-detail-info-item">本子ID: ${task.album_ids.join(', ')}</div>
                  ` : task.album_ids.length > 5 ? `
                    <div class="task-detail-info-item">本子ID: ${task.album_ids.slice(0, 3).join(', ')} ... 等${task.album_ids.length}个</div>
                  ` : ''}
                  ${task.photo_ids.length > 0 && task.photo_ids.length <= 5 ? `
                    <div class="task-detail-info-item">章节ID: ${task.photo_ids.join(', ')}</div>
                  ` : task.photo_ids.length > 5 ? `
                    <div class="task-detail-info-item">章节ID: ${task.photo_ids.slice(0, 3).join(', ')} ... 等${task.photo_ids.length}个</div>
                  ` : ''}
                ` : `
                  <div class="task-detail-info-item">账号: ${task.config?.username || '未知'}</div>
                `}
                <div class="task-detail-info-item">速度限制: ${formatSpeedLimit(task.config?.speed_limit)}${task.config?.speed_limit > 0 ? '/s' : ''}</div>
                ${task.config?.download_dir ? `<div class="task-detail-info-item">下载目录: ${task.config.download_dir}</div>` : ''}
                ${task.start_time ? `<div class="task-detail-info-item">开始时间: ${formatTime(task.start_time)}</div>` : ''}
                ${task.end_time ? `<div class="task-detail-info-item">结束时间: ${formatTime(task.end_time)}</div>` : ''}
                ${task.status === 'completed' && task.start_time && task.end_time ? 
                  `<div class="task-detail-info-item">耗时: ${formatDuration(task.start_time, task.end_time)}</div>` : ''}
                ${task.error ? `<div class="task-detail-info-item" style="color: #ef4444;">错误: ${task.error}</div>` : ''}
              </div>
            </div>
            
            <!-- 详细日志加载占位 -->
            <div class="task-detail-section">
              <div class="task-detail-title">详细日志</div>
              <div class="task-detail-logs" id="log-task-logs-${task.id}">
                ${manualTaskLogsCache[task.id] || '<div class="loading-placeholder" style="color: #9ca3af; text-align: center;">正在加载日志...</div>'}
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
  
  // 恢复滚动位置（使用 requestAnimationFrame 确保 DOM 已更新）
  requestAnimationFrame(() => {
    if (scrollTop > 0) {
      logList.scrollTop = scrollTop;
    }
  });
  
  // 异步更新展开任务的日志（running 任务或缓存已清除的任务）
  manualExpandedTasks.forEach(async (taskId) => {
    const task = filteredTasks.find(t => t.id === taskId);
    // 更新条件：任务正在运行 OR 缓存已被清除（需要重新加载）
    if (task && (task.status === 'running' || !manualTaskLogsCache[taskId])) {
      try {
        const response = await fetch(`${API_BASE}/api/realtime_logs/${taskId}`);
        if (!response.ok) return;
        const logs = await response.json();
        
        const logsHtml = logs && logs.length > 0 
          ? logs.map(line => `<div class="task-detail-log-line">${line}</div>`).join('')
          : '<div style="color: #9ca3af; text-align: center; padding: 20px;">暂无详细日志</div>';
        
        // 更新缓存
        manualTaskLogsCache[taskId] = logsHtml;
        
        // 更新 DOM（如果元素还存在）
        const logsContainer = document.getElementById(`log-task-logs-${taskId}`);
        if (logsContainer) {
          logsContainer.innerHTML = logsHtml;
        }
      } catch (error) {
        // 静默失败，不影响用户体验
      }
    }
  });
}

// 切换执行日志中的任务详情展开/收起
async function toggleLogTaskDetail(taskId) {
  const detailContent = document.getElementById(`log-task-detail-${taskId}`);
  const expandIcon = document.getElementById(`log-task-expand-icon-${taskId}`);
  const logsContainer = document.getElementById(`log-task-logs-${taskId}`);
  
  if (detailContent && expandIcon) {
    if (detailContent.classList.contains('expanded')) {
      // 收起
      detailContent.classList.remove('expanded');
      expandIcon.classList.remove('expanded');
      manualExpandedTasks.delete(taskId);
    } else {
      // 展开
      detailContent.classList.add('expanded');
      expandIcon.classList.add('expanded');
      manualExpandedTasks.add(taskId);
      
      // 加载详细日志（只在缓存中没有时加载）
      if (logsContainer && !manualTaskLogsCache[taskId]) {
        // 显示加载中状态
        logsContainer.innerHTML = '<div style="color: #9ca3af; text-align: center; padding: 20px;">正在加载日志...</div>';
        
        try {
          const response = await fetch(`${API_BASE}/api/realtime_logs/${taskId}`);
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          const logs = await response.json();
          
          let logsHtml;
          if (logs && logs.length > 0) {
            logsHtml = logs.map(line => `<div class="task-detail-log-line">${line}</div>`).join('');
          } else {
            logsHtml = '<div style="color: #9ca3af; text-align: center; padding: 20px;">暂无详细日志</div>';
          }
          
          // 缓存日志内容
          manualTaskLogsCache[taskId] = logsHtml;
          logsContainer.innerHTML = logsHtml;
        } catch (error) {
          console.error('加载日志失败:', error);
          const errorHtml = '<div style="color: #ef4444; text-align: center; padding: 20px;">加载日志失败: ' + error.message + '</div>';
          manualTaskLogsCache[taskId] = errorHtml;
          logsContainer.innerHTML = errorHtml;
        }
      }
    }
  }
}

function updateManualStats() {
  const total = manualTasksCache.length;
  const running = manualTasksCache.filter(task => task.status === 'running').length;
  const completed = manualTasksCache.filter(task => task.status === 'completed').length;
  const failed = manualTasksCache.filter(task => task.status === 'failed').length;
  
  document.getElementById('manualStatTotal').textContent = total;
  document.getElementById('manualStatInfo').textContent = running;
  document.getElementById('manualStatSuccess').textContent = completed;
  document.getElementById('manualStatError').textContent = failed;
}

// 自动化日志逻辑已迁移至 logs.js

// 加载日志
async function loadLogs() {
  try {
    const taskFilter = document.getElementById('filterTask').value;
    const levelFilter = document.getElementById('filterLevel').value;
    
    let url = `${API_BASE}/api/logs?limit=100`;
    if (taskFilter !== 'all') url += `&task_id=${taskFilter}`;
    if (levelFilter !== 'all') url += `&level=${levelFilter}`;
    
    const response = await fetch(url);
    const logs = await response.json();
    
    const logList = document.getElementById('logList');
    
    if (logs.length === 0) {
      logList.innerHTML = '<div class="empty-state">暂无日志</div>';
      return;
    }
    
    logList.innerHTML = logs.map(log => `
      <div class="log-item ${log.level}">
        <div class="log-header">
          <div class="log-meta">
            <span class="status-badge ${log.level}">${log.level}</span>
            <span>任务 #${log.task_id}</span>
          </div>
          <span class="log-time">${formatTime(log.timestamp)}</span>
        </div>
        <div class="log-message">${log.message}</div>
      </div>
    `).join('');
  } catch (error) {
    console.error('加载日志失败:', error);
  }
}

// 加载统计信息
async function loadStats() {
  try {
    const response = await fetch(`${API_BASE}/api/stats`);
    const stats = await response.json();
    
    document.getElementById('statTotalTasks').textContent = stats.total_tasks;
    document.getElementById('statRunning').textContent = stats.running;
    document.getElementById('statCompleted').textContent = stats.completed;
    document.getElementById('statFailed').textContent = stats.failed;
    document.getElementById('statPending').textContent = stats.pending;
  } catch (error) {
    console.error('加载统计失败:', error);
  }
}

// 更新任务筛选器
async function updateTaskFilter() {
  try {
    const response = await fetch(`${API_BASE}/api/tasks`);
    const tasks = await response.json();
    
    const filterTask = document.getElementById('filterTask');
    const currentValue = filterTask.value;
    
    filterTask.innerHTML = '<option value="all">全部</option>';
    tasks.forEach(task => {
      const option = document.createElement('option');
      option.value = task.id;
      option.textContent = `任务 #${task.id} - ${task.type === 'download' ? '下载' : '导出'}`;
      filterTask.appendChild(option);
    });
    
    // 恢复选择
    if (currentValue !== 'all') {
      filterTask.value = currentValue;
    }
  } catch (error) {
    console.error('更新筛选器失败:', error);
  }
}

// 定时刷新
let refreshInterval = null;

function startAutoRefresh() {
  if (refreshInterval) return;
  
  refreshInterval = setInterval(() => {
    const activeTab = document.querySelector('.tab-content.active');
    
    // 手动下载页面刷新
    if (activeTab && activeTab.dataset.content === 'manual') {
      loadManualLogs();
    }
  }, 3000); // 每3秒刷新一次
}

function stopAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
}

// 操作切换（下载/导出）
function initOperationSwitch() {
  const switchBtns = document.querySelectorAll('.switch-btn');
  const operationContents = document.querySelectorAll('.operation-content');
  
  switchBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const operation = btn.dataset.operation;
      
      // 更新按钮状态
      switchBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      // 更新内容显示
      operationContents.forEach(content => {
        if (content.dataset.operationContent === operation) {
          content.classList.add('active');
        } else {
          content.classList.remove('active');
        }
      });
    });
  });
}

// 自动化任务管理已迁移至 automation 模块

// 初始化已迁移到 bootstrap.js

// 初始化日志筛选器
function initLogFilters() {
  // 手动下载日志筛选器
  document.getElementById('manualFilterLevel')?.addEventListener('change', applyManualFilters);
  document.getElementById('manualFilterTimeRange')?.addEventListener('change', applyManualFilters);
  document.getElementById('manualFilterKeyword')?.addEventListener('input', applyManualFilters);
  document.getElementById('refreshManualLogs')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.classList.add('refreshing');
    
    // 清除正在运行的任务的日志缓存，以便加载最新日志
    manualTasksCache.forEach(task => {
      if (task.status === 'running' && manualTaskLogsCache[task.id]) {
        delete manualTaskLogsCache[task.id];
      }
    });
    
    await loadManualLogs();
    setTimeout(() => btn.classList.remove('refreshing'), 600);
  });
  
  // 自动化日志筛选器已迁移至 automation 模块
}

// ==================== 表单数据持久化 ====================

const STORAGE_KEY = 'jmcomic_form_data';

/**
 * 保存表单数据到 localStorage
 */
function saveFormData() {
  const data = {
    // 下载本子配置
    download: {
      downloadDir: document.getElementById('downloadDir')?.value || '',
      dirRule: document.getElementById('dirRule')?.value || '',
      clientImpl: document.getElementById('clientImpl')?.value || '',
      imageSuffix: document.getElementById('imageSuffix')?.value || '',
      downloadSpeed: document.getElementById('downloadSpeed')?.value || '',
      dlUsername: document.getElementById('dlUsername')?.value || '',
      dlPassword: document.getElementById('dlPassword')?.value || '',
    },
    // 导出收藏夹配置
    export: {
      expUsername: document.getElementById('expUsername')?.value || '',
      expPassword: document.getElementById('expPassword')?.value || '',
      zipEnable: document.getElementById('zipEnable')?.value || '',
      zipPassword: document.getElementById('zipPassword')?.value || '',
      saveDir: document.getElementById('saveDir')?.value || '',
      zipFilepath: document.getElementById('zipFilepath')?.value || '',
    },
    // 自动化任务默认配置
    automation: {
      autoDownloadDir: document.getElementById('autoDownloadDir')?.value || '',
      autoClientImpl: document.getElementById('autoClientImpl')?.value || '',
      autoImageSuffix: document.getElementById('autoImageSuffix')?.value || '',
      autoDownloadSpeed: document.getElementById('autoDownloadSpeed')?.value || '',
    }
  };
  
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.error('保存表单数据失败:', e);
  }
}

/**
 * 从 localStorage 恢复表单数据
 */
function loadFormData() {
  try {
    const savedData = localStorage.getItem(STORAGE_KEY);
    if (!savedData) return;
    
    const data = JSON.parse(savedData);
    
    // 恢复下载本子配置
    if (data.download) {
      setInputValue('downloadDir', data.download.downloadDir);
      setInputValue('dirRule', data.download.dirRule);
      setSelectValue('clientImpl', data.download.clientImpl);
      setSelectValue('imageSuffix', data.download.imageSuffix);
      setInputValue('downloadSpeed', data.download.downloadSpeed);
      setInputValue('dlUsername', data.download.dlUsername);
      setInputValue('dlPassword', data.download.dlPassword);
    }
    
    // 恢复导出收藏夹配置
    if (data.export) {
      setInputValue('expUsername', data.export.expUsername);
      setInputValue('expPassword', data.export.expPassword);
      setSelectValue('zipEnable', data.export.zipEnable);
      setInputValue('zipPassword', data.export.zipPassword);
      setInputValue('saveDir', data.export.saveDir);
      setInputValue('zipFilepath', data.export.zipFilepath);
    }
    
    // 恢复自动化任务默认配置
    if (data.automation) {
      setInputValue('autoDownloadDir', data.automation.autoDownloadDir);
      setSelectValue('autoClientImpl', data.automation.autoClientImpl);
      setSelectValue('autoImageSuffix', data.automation.autoImageSuffix);
      setInputValue('autoDownloadSpeed', data.automation.autoDownloadSpeed);
    }
  } catch (e) {
    console.error('恢复表单数据失败:', e);
  }
}

/**
 * 设置输入框的值
 */
function setInputValue(id, value) {
  const element = document.getElementById(id);
  if (element && value) {
    element.value = value;
  }
}

/**
 * 设置下拉框的值并更新自定义下拉菜单显示
 */
function setSelectValue(id, value) {
  const element = document.getElementById(id);
  if (element && value) {
    element.value = value;
    updateCustomSelectText(element);
  }
}

/**
 * 为表单元素添加自动保存监听器
 */
function initAutoSave() {
  // 需要自动保存的表单元素ID列表
  const formIds = [
    // 下载本子
    'downloadDir', 'dirRule', 'clientImpl', 'imageSuffix', 'downloadSpeed', 'dlUsername', 'dlPassword',
    // 导出收藏夹
    'expUsername', 'expPassword', 'zipEnable', 'zipPassword', 'saveDir', 'zipFilepath',
    // 自动化
    'autoDownloadDir', 'autoClientImpl', 'autoImageSuffix', 'autoDownloadSpeed'
  ];
  
  formIds.forEach(id => {
    const element = document.getElementById(id);
    if (element) {
      // 监听输入事件（input 和 change）
      element.addEventListener('input', saveFormData);
      element.addEventListener('change', saveFormData);
    }
  });
}

// 自定义下拉菜单已迁移至 select.js

// 暴露全局函数（供内联事件使用）
window.toggleLogTaskDetail = toggleLogTaskDetail;

