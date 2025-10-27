import { API_BASE } from './config.js';
import { formatTime, formatDuration, formatSpeedLimit, showMessage, showConfirm } from './utils.js';
let manualTasksCache = [];
let manualExpandedTasks = new Set();
let manualTaskLogsCache = {};
let manualCurrentPage = 1;  // 当前页码
let manualFilteredTasks = [];  // 过滤后的任务列表

async function loadManualLogs() {
  try {
    const response = await fetch(`${API_BASE}/api/tasks`);
    const allTasks = await response.json();
    const newManualTasks = allTasks.filter(t => !t.auto_task_id);

    newManualTasks.forEach(task => {
      if ((task.status === 'completed' || task.status === 'failed') && manualTaskLogsCache[task.id]) {
        const oldTask = manualTasksCache.find(t => t.id === task.id);
        if (oldTask && oldTask.status === 'running') delete manualTaskLogsCache[task.id];
      }
    });

    // 按创建时间排序，最新的在前
    newManualTasks.sort((a, b) => {
      const timeA = new Date(a.create_time || 0).getTime();
      const timeB = new Date(b.create_time || 0).getTime();
      return timeB - timeA;  // 降序：最新的在前
    });

    manualTasksCache = newManualTasks;
    applyManualFilters();
    updateManualStats();
  } catch (error) {
    console.error('加载手动日志失败:', error);
  }
}

function applyManualFilters(resetPage = true) {
  const filterLevel = document.getElementById('manualFilterLevel')?.value || 'all';
  const filterTimeRange = document.getElementById('manualFilterTimeRange')?.value || 'all';
  const filterKeyword = document.getElementById('manualFilterKeyword')?.value.toLowerCase() || '';

  let filteredTasks = [...manualTasksCache];
  if (filterLevel !== 'all') {
    const statusMap = { 'info': 'running', 'success': 'completed', 'error': 'failed' };
    const targetStatus = statusMap[filterLevel];
    if (targetStatus) filteredTasks = filteredTasks.filter(task => task.status === targetStatus);
  }
  if (filterTimeRange !== 'all') {
    const hours = parseInt(filterTimeRange);
    const cutoffTime = Date.now() - (hours * 3600 * 1000);
    filteredTasks = filteredTasks.filter(task => new Date(task.create_time).getTime() > cutoffTime);
  }
  if (filterKeyword) {
    filteredTasks = filteredTasks.filter(task => {
      const taskLabel = task.type === 'download' ? '下载' : '导出';
      const searchText = `${taskLabel} ${task.type} ${task.status} ${task.username || task.config?.username || ''}`.toLowerCase();
      return searchText.includes(filterKeyword);
    });
  }

  const logList = document.getElementById('manualLogsList');
  if (!logList) return;
  const scrollTop = logList.scrollTop;

  if (filteredTasks.length === 0) {
    if (logList.innerHTML !== '<div class="empty-state">暂无符合条件的任务</div>') {
      logList.innerHTML = '<div class="empty-state">暂无符合条件的任务</div>';
    }
    return;
  }

  // 保存过滤后的任务列表（已经按时间降序排列，最新的在前）
  manualFilteredTasks = filteredTasks;
  
  // 筛选条件改变时重置到第一页
  if (resetPage) {
    manualCurrentPage = 1;
  }
  
  // 分页逻辑
  const pageSize = 10;
  const totalPages = Math.ceil(manualFilteredTasks.length / pageSize);
  
  // 确保当前页在有效范围内
  if (manualCurrentPage > totalPages) {
    manualCurrentPage = totalPages;
  }
  if (manualCurrentPage < 1) {
    manualCurrentPage = 1;
  }
  
  const startIndex = (manualCurrentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const tasksToShow = manualFilteredTasks.slice(startIndex, endIndex);
  const newTaskIds = new Set(tasksToShow.map(t => t.id));
  const existingTaskEls = Array.from(logList.querySelectorAll('.task-item'));
  const existingTaskIds = new Set(existingTaskEls.map(el => parseInt(el.dataset.taskId, 10)));

  // 增量更新：只更新需要变化的部分
  let needsFullRebuild = false;
  
  // 检查是否需要完全重建（顺序变化或大量新增/删除）
  if (existingTaskEls.length === 0 || 
      newTaskIds.size !== existingTaskIds.size ||
      tasksToShow.length !== existingTaskEls.length) {
    needsFullRebuild = true;
  } else {
    // 检查顺序是否变化
    for (let i = 0; i < tasksToShow.length; i++) {
      const expectedId = tasksToShow[i].id;
      const actualId = parseInt(existingTaskEls[i].dataset.taskId, 10);
      if (expectedId !== actualId) {
        needsFullRebuild = true;
        break;
      }
    }
  }

  if (needsFullRebuild) {
    // 全量重建（过滤条件变化或新任务）
    const tasksHtml = tasksToShow.map(task => renderTaskCard(task)).join('');
    const paginationHtml = renderManualPagination();
    const html = tasksHtml + paginationHtml;
    
    if (logList._lastHtml !== html) {
      logList._lastHtml = html;
      logList.classList.add('no-transitions');
      logList.innerHTML = html;
      requestAnimationFrame(() => {
        if (scrollTop > 0) logList.scrollTop = scrollTop;
        requestAnimationFrame(() => logList.classList.remove('no-transitions'));
      });
      setTimeout(() => logList.classList.remove('no-transitions'), 250);
    }
  } else {
    // 增量更新：仅更新状态变化的任务
    tasksToShow.forEach((task, index) => {
      const taskEl = existingTaskEls[index];
      const currentStatus = taskEl.className.match(/task-item (\w+)/)?.[1];
      
      // 仅当状态变化时更新
      if (currentStatus !== task.status) {
        updateTaskStatus(taskEl, task);
      }
    });
  }

  // 异步更新展开任务的日志
  manualExpandedTasks.forEach(async (taskId) => {
    const task = tasksToShow.find(t => t.id === taskId);
    if (task && (task.status === 'running' || !manualTaskLogsCache[taskId])) {
      try {
        const response = await fetch(`${API_BASE}/api/task_snapshot/${taskId}?limit=200`);
        if (!response.ok) return;
        const snapshot = await response.json();
        const logs = (snapshot.logs || []).map(entry => {
          if (typeof entry === 'string') return entry;
          try {
            const ts = entry.timestamp ? entry.timestamp.replace('T', ' ').slice(0, 19) : '';
            const level = entry.level || 'info';
            const msg = entry.message || JSON.stringify(entry);
            const emoji = level === 'success' ? '✅' : level === 'error' ? '❌' : 'ℹ️';
            return `[${ts}] ${emoji} ${msg}`;
          } catch { return String(entry); }
        });
        const currentTask = snapshot.task || task;
        const logsHtml = logs && logs.length > 0 ? logs.map(line => `<div class="task-detail-log-line">${line}</div>`).join('') : '<div style="color: #9ca3af; text-align: center; padding: 20px;">暂无详细日志</div>';
        manualTaskLogsCache[taskId] = logsHtml;
        const logsContainer = document.getElementById(`log-task-logs-${taskId}`);
        if (logsContainer) logsContainer.innerHTML = logsHtml;
        if (currentTask && currentTask.status === 'completed') {
          setTaskStatusCompleted(taskId);
        }
      } catch (e) { /* ignore */ }
    }
  });
}

// 渲染单个任务卡片的辅助函数
function renderTaskCard(task) {
  const summary = task.type === 'download' ? `${task.album_ids.length}个本子, ${task.photo_ids.length}个章节` : `账号: ${task.username || task.config?.username || '未知'}`;
  const taskLabel = task.type === 'download' ? '下载' : '导出';
  const isExpanded = manualExpandedTasks.has(task.id);
  return `
    <div class="task-item ${task.status}" data-task-id="${task.id}">
      <div class="task-item-header" data-action="toggle" data-task-id="${task.id}">
        <span class="task-expand-icon ${isExpanded ? 'expanded' : ''}" id="log-task-expand-icon-${task.id}">▶</span>
        <span class="task-status-badge ${task.status}">${task.status === 'running' ? '运行中' : task.status === 'completed' ? '已完成' : task.status === 'failed' ? '失败' : '等待中'}</span>
        <span class="task-id">${taskLabel}</span>
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
          <div class="task-detail-section">
            <div class="task-detail-title">详细信息</div>
            <div class="task-detail-info task-detail-info-grid">
              <div class="task-detail-info-item">类型: ${task.type === 'download' ? '下载本子' : '导出收藏夹'}</div>
              ${task.type === 'download' ? `
                <div class="task-detail-info-item">本子数: ${task.album_ids.length}，章节数: ${task.photo_ids.length}</div>
              ` : `
                <div class="task-detail-info-item">账号: ${task.username || task.config?.username || '未知'}</div>
              `}
              <div class="task-detail-info-item">速度限制: ${formatSpeedLimit(task.config?.speed_limit)}${task.config?.speed_limit > 0 ? '/s' : ''}</div>
              ${task.config?.download_dir ? `<div class="task-detail-info-item">下载目录: ${task.config.download_dir}</div>` : ''}
              ${task.start_time ? `<div class="task-detail-info-item">开始时间: ${formatTime(task.start_time)}</div>` : ''}
              ${task.end_time ? `<div class="task-detail-info-item">结束时间: ${formatTime(task.end_time)}</div>` : ''}
              ${task.status === 'completed' && task.start_time && task.end_time ? `<div class="task-detail-info-item">耗时: ${formatDuration(task.start_time, task.end_time)}</div>` : ''}
              ${task.error ? `<div class="task-detail-info-item" style="color: #ef4444;">错误: ${task.error}</div>` : ''}
            </div>
          </div>
          <div class="task-detail-section">
            <div class="task-detail-title">详细日志</div>
            <div class="task-detail-logs" id="log-task-logs-${task.id}">
              ${manualTaskLogsCache[task.id] || '<div class="loading-placeholder" style="color: #9ca3af; text-align: center;">正在加载日志...</div>'}
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

// 更新任务状态的辅助函数
function updateTaskStatus(taskEl, task) {
  // 更新任务项类名
  taskEl.className = `task-item ${task.status}`;
  
  // 更新状态徽章
  const badge = taskEl.querySelector('.task-status-badge');
  if (badge) {
    const statusText = task.status === 'running' ? '运行中' : 
                       task.status === 'completed' ? '已完成' : 
                       task.status === 'failed' ? '失败' : '等待中';
    badge.className = `task-status-badge ${task.status}`;
    badge.textContent = statusText;
  }
  
  // 更新操作按钮（running状态不显示删除按钮）
  const actionsContainer = taskEl.querySelector('.task-actions-compact');
  if (actionsContainer) {
    if (task.status === 'running') {
      actionsContainer.innerHTML = '';
    } else if (actionsContainer.children.length === 0) {
      actionsContainer.innerHTML = `
        <button class="icon-delete-btn" data-action="delete" data-task-id="${task.id}" title="删除">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
          </svg>
        </button>`;
    }
  }
}

async function toggleLogTaskDetail(taskId) {
  const detailContent = document.getElementById(`log-task-detail-${taskId}`);
  const expandIcon = document.getElementById(`log-task-expand-icon-${taskId}`);
  const logsContainer = document.getElementById(`log-task-logs-${taskId}`);
  if (detailContent && expandIcon) {
    if (detailContent.classList.contains('expanded')) {
      detailContent.classList.remove('expanded');
      expandIcon.classList.remove('expanded');
      manualExpandedTasks.delete(taskId);
    } else {
      detailContent.classList.add('expanded');
      expandIcon.classList.add('expanded');
      manualExpandedTasks.add(taskId);
      
      // 总是加载日志（包括历史任务）
      if (logsContainer) {
        logsContainer.innerHTML = '<div style="color: #9ca3af; text-align: center; padding: 20px;">正在加载日志...</div>';
        try {
          const response = await fetch(`${API_BASE}/api/realtime_logs/${taskId}`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const raw = await response.json();
          const logs = (raw || []).map(line => {
            if (typeof line === 'string') return line;
            try { return JSON.stringify(line); } catch { return String(line); }
          });
          const logsHtml = logs && logs.length > 0 ? logs.map(line => `<div class="task-detail-log-line">${line}</div>`).join('') : '<div style="color: #9ca3af; text-align: center; padding: 20px;">暂无详细日志</div>';
          manualTaskLogsCache[taskId] = logsHtml;
          logsContainer.innerHTML = logsHtml;
          if (Array.isArray(logs) && logs.some(line => line.includes('✅') || line.includes('下载完成'))) {
            setTaskStatusCompleted(taskId);
          }
        } catch (error) {
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
      </div>`).join('');
  } catch (e) { console.error('加载日志失败:', e); }
}
/**
 * 渲染手动下载日志的分页控制器
 */
function renderManualPagination() {
  const pageSize = 10;
  const totalPages = Math.ceil(manualFilteredTasks.length / pageSize);
  
  if (totalPages <= 1) return '';
  
  return `
    <div class="manual-logs-pagination">
      <button 
        class="pagination-arrow-btn ${manualCurrentPage === 1 ? 'disabled' : ''}" 
        id="manualPrevPage"
        ${manualCurrentPage === 1 ? 'disabled' : ''}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="pagination-page-info">第 ${manualCurrentPage} 页 / 共 ${totalPages} 页</span>
      <button 
        class="pagination-arrow-btn ${manualCurrentPage === totalPages ? 'disabled' : ''}" 
        id="manualNextPage"
        ${manualCurrentPage === totalPages ? 'disabled' : ''}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </button>
    </div>`;
}

/**
 * 切换到上一页
 */
function goToPrevPage() {
  if (manualCurrentPage > 1) {
    manualCurrentPage--;
    applyManualFilters(false);
  }
}

/**
 * 切换到下一页
 */
function goToNextPage() {
  const totalPages = Math.ceil(manualFilteredTasks.length / 10);
  if (manualCurrentPage < totalPages) {
    manualCurrentPage++;
    applyManualFilters(false);
  }
}

// 添加分页按钮的事件监听
document.addEventListener('click', (e) => {
  if (e.target.closest('#manualPrevPage')) {
    goToPrevPage();
  } else if (e.target.closest('#manualNextPage')) {
    goToNextPage();
  }
});

export { loadManualLogs, applyManualFilters, toggleLogTaskDetail, updateManualStats, loadLogs };

document.addEventListener('click', async (e) => {
  // 先检查是否点击了删除按钮或其子元素
  // 只处理手动任务区域内的删除按钮（通过检查是否在 manualLogsList 内）
  const delBtn = e.target.closest('.icon-delete-btn');
  const manualLogsContainer = document.getElementById('manualLogsList');
  if (delBtn && manualLogsContainer && manualLogsContainer.contains(delBtn)) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    const id = parseInt(delBtn.dataset.taskId, 10);
    const confirmed = await showConfirm('确定要删除这个任务吗？');
    if (!confirmed) return;
    try {
      const response = await fetch(`${API_BASE}/api/tasks/${id}`, { method: 'DELETE' });
      if (response.ok) {
        loadManualLogs();
      } else {
        const data = await response.json();
        showMessage(`删除失败: ${data.error}`, 'error');
      }
    } catch (error) {
      showMessage(`请求失败: ${error.message}`, 'error');
    }
    return;
  }
  
  // 检查是否点击了操作按钮区域
  if (e.target.closest('.task-actions-compact')) {
    return; // 不处理操作区域的点击
  }
  
  // 再检查任务头部的展开/折叠
  const toggleArea = e.target.closest('[data-action="toggle"]');
  if (toggleArea) {
    const id = parseInt(toggleArea.dataset.taskId, 10);
    await toggleLogTaskDetail(id);
    return;
  }
});

function setTaskStatusCompleted(taskId) {
  const item = document.querySelector(`.task-item[data-task-id="${taskId}"]`);
  if (!item) return;
  item.classList.remove('running', 'pending', 'failed');
  item.classList.add('completed');
  const badge = item.querySelector('.task-status-badge');
  if (badge) {
    badge.className = 'task-status-badge completed';
    badge.textContent = '已完成';
  }
}


