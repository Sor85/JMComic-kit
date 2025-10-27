/**
 * UI 渲染函数
 * 
 * 负责渲染自动化任务列表、执行历史等UI组件
 */
import { formatTime, formatSpeedLimit, formatDuration } from '../utils.js';

/**
 * 渲染自动化任务卡片
 */
export function renderTaskCard(task, executions, isExpanded, currentPage = 1) {
  // 分页处理
  const pageSize = 10;
  const totalPages = Math.ceil(executions.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const pageExecutions = executions.slice(startIndex, endIndex);
  
  const executionsList = renderExecutionsList(pageExecutions);
  const paginationHtml = totalPages > 1 ? renderPagination(task.id, currentPage, totalPages, executions.length) : '';
  
  return `
    <div class="auto-task-card ${task.status}">
      <div class="auto-task-header">
        <div class="auto-task-title">${task.name}</div>
        <span class="status-badge ${task.status}">${task.status === 'running' ? '运行中' : '已停止'}</span>
      </div>
      <div class="auto-task-meta">
        <div class="auto-task-meta-item"><span class="auto-task-meta-label">账号：</span><span class="auto-task-meta-value">${task.username}</span></div>
        <div class="auto-task-meta-item"><span class="auto-task-meta-label">Cron：</span><span class="auto-task-meta-value">${task.cron}</span></div>
        <div class="auto-task-meta-item"><span class="auto-task-meta-label">下载目录：</span><span class="auto-task-meta-value">${task.download_dir}</span></div>
        <div class="auto-task-meta-item"><span class="auto-task-meta-label">速度限制：</span><span class="auto-task-meta-value">${formatSpeedLimit(task.speed_limit)}${task.speed_limit > 0 ? '/s' : ''}</span></div>
        <div class="auto-task-meta-item"><span class="auto-task-meta-label">下次执行：</span><span class="auto-task-meta-value">${task.next_run ? formatTime(task.next_run) : '-'}</span></div>
      </div>
      <div class="auto-task-stats">
        <div class="auto-task-stat"><div class="auto-task-stat-label">总运行次数</div><div class="auto-task-stat-value">${task.run_count || 0}</div></div>
        <div class="auto-task-stat"><div class="auto-task-stat-label">已下载</div><div class="auto-task-stat-value">${task.downloaded_count || 0}</div></div>
        <div class="auto-task-stat"><div class="auto-task-stat-label">已跳过</div><div class="auto-task-stat-value">${task.skipped_count || 0}</div></div>
        <div class="auto-task-stat"><div class="auto-task-stat-label">本月新增</div><div class="auto-task-stat-value" style="color: #10b981;">${task.monthly_new_count || 0}</div></div>
        <div class="auto-task-stat"><div class="auto-task-stat-label">上次运行</div><div class="auto-task-stat-value" style="font-size: 12px;">${task.last_run ? formatTime(task.last_run).split(' ')[1] : '-'}</div></div>
      </div>
      <div class="auto-task-actions">
        ${renderTaskActions(task)}
      </div>
      
      <!-- 执行历史区域 -->
      <div class="auto-task-executions">
        <button class="auto-task-executions-toggle" data-action="toggle-executions" data-task-id="${task.id}">
          <span class="toggle-icon ${isExpanded ? 'expanded' : ''}">▶</span>
          <span>执行历史 (${executions.length})</span>
        </button>
        <div class="auto-task-executions-list ${isExpanded ? 'expanded' : ''}" id="executions-list-${task.id}">
          ${executionsList}
          ${paginationHtml}
        </div>
      </div>
    </div>`;
}

/**
 * 渲染任务操作按钮
 */
function renderTaskActions(task) {
  const startStopButton = task.status === 'stopped' ? `
    <button class="icon-start-btn" data-action="auto-start" data-task-id="${task.id}" title="启动">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
    </button>` : `
    <button class="icon-stop-btn" data-action="auto-stop" data-task-id="${task.id}" title="停止">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
    </button>`;
  
  return `
    ${startStopButton}
    <button class="icon-run-btn" data-action="auto-run" data-task-id="${task.id}" title="立即执行">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
    </button>
    <button class="icon-edit-btn" data-action="auto-edit" data-task-id="${task.id}" title="编辑">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
    </button>
    <button class="icon-delete-btn" data-action="auto-delete" data-task-id="${task.id}" title="删除">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
    </button>`;
}

/**
 * 渲染执行历史列表
 */
export function renderExecutionsList(executions) {
  if (executions.length === 0) {
    return '<div class="empty-state" style="padding: 16px; font-size: 13px;">暂无执行记录</div>';
  }
  
  return executions.map(ex => {
    const statusText = ex.status === 'running' ? '运行中' : ex.status === 'completed' ? '已完成' : '失败';
    const statusClass = ex.status === 'running' ? 'running' : ex.status === 'completed' ? 'completed' : 'failed';
    const duration = ex.end_time ? formatDuration(ex.start_time, ex.end_time) : '进行中';
    
    return `
      <div class="execution-item ${statusClass}" data-action="view-execution" data-execution-id="${ex.id}">
        <div class="execution-item-header">
          <span class="execution-status-badge ${statusClass}">${statusText}</span>
          <span class="execution-time">${formatTime(ex.start_time)}</span>
        </div>
        <div class="execution-item-body">
          <div class="execution-item-stats">
            <span class="execution-stat">扫描: <b>${ex.scanned_count || 0}</b></span>
            <span class="execution-stat">下载: <b>${ex.to_download_count || 0}</b></span>
            <span class="execution-stat">跳过: <b>${ex.skipped_count || 0}</b></span>
            <span class="execution-stat">耗时: <b>${duration}</b></span>
          </div>
          ${ex.status !== 'running' ? `
            <button class="icon-delete-btn" data-action="delete-execution" data-execution-id="${ex.id}" data-task-id="${ex.auto_task_id}" title="删除">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
              </svg>
            </button>
          ` : ''}
        </div>
      </div>`;
  }).join('');
}

/**
 * 渲染执行详情统计信息
 */
export function renderExecutionStats(execution) {
  const statusText = execution.status === 'running' ? '运行中' : execution.status === 'completed' ? '已完成' : '失败';
  const statusClass = execution.status;
  const duration = execution.end_time ? formatDuration(execution.start_time, execution.end_time) : '进行中';
  
  return `
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">状态</span>
      <span class="execution-status-badge ${statusClass}">${statusText}</span>
    </div>
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">开始时间</span>
      <span class="execution-modal-stat-value">${formatTime(execution.start_time)}</span>
    </div>
    ${execution.end_time ? `
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">结束时间</span>
      <span class="execution-modal-stat-value">${formatTime(execution.end_time)}</span>
    </div>` : ''}
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">耗时</span>
      <span class="execution-modal-stat-value">${duration}</span>
    </div>
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">扫描数量</span>
      <span class="execution-modal-stat-value">${execution.scanned_count || 0}</span>
    </div>
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">本地已有</span>
      <span class="execution-modal-stat-value">${execution.local_count || 0}</span>
    </div>
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">需要下载</span>
      <span class="execution-modal-stat-value">${execution.to_download_count || 0}</span>
    </div>
    <div class="execution-modal-stat-item">
      <span class="execution-modal-stat-label">跳过数量</span>
      <span class="execution-modal-stat-value">${execution.skipped_count || 0}</span>
    </div>
    ${execution.error ? `
    <div class="execution-modal-stat-item" style="grid-column: 1 / -1;">
      <span class="execution-modal-stat-label">错误</span>
      <span class="execution-modal-stat-value" style="color: #ef4444;">${execution.error}</span>
    </div>` : ''}`;
}

/**
 * 渲染关联任务列表
 */
export function renderRelatedTasks(tasks) {
  if (!tasks || tasks.length === 0) {
    return '';
  }
  
  return tasks.map(task => {
    const statusText = task.status === 'running' ? '运行中' : 
                       task.status === 'completed' ? '已完成' :
                       task.status === 'partial_success' ? '部分成功' :
                       task.status === 'failed' ? '失败' :
                       task.status === 'pending' ? '等待中' : '未知';
    
    // 检查是否有失败的图片
    const failedImages = task.failed_images || [];
    const hasFailedImages = failedImages.length > 0;
    const failedCount = failedImages.length;
    
    // 显示失败图片信息和重试按钮
    const failedInfo = hasFailedImages ? `
      <div class="execution-modal-task-failed">
        <span class="failed-count">失败图片: ${failedCount} 张</span>
        <button class="btn-retry-failed" data-task-id="${task.id}" title="重试失败的图片">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 4v6h6M23 20v-6h-6"/>
            <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>
          </svg>
          重试
        </button>
      </div>` : '';
    
    return `
      <div class="execution-modal-task-item ${hasFailedImages ? 'has-failures' : ''}">
        <div class="execution-modal-task-main">
          <span class="execution-modal-task-id">任务 #${task.id}</span>
          <span class="execution-modal-task-status ${task.status}">${statusText}</span>
          <span class="execution-modal-task-info">${task.album_ids.length} 个本子</span>
        </div>
        ${failedInfo}
      </div>`;
  }).join('');
}

/**
 * 渲染执行日志
 */
export function renderExecutionLogs(syncLogs, taskLogsResults) {
  let allLogsHtml = '';
  
  // 1. 显示自动化同步日志
  if (syncLogs.length > 0) {
    allLogsHtml += '<div class="execution-modal-log-section-title">📋 自动化同步阶段</div>';
    allLogsHtml += syncLogs.map(line => 
      `<div class="execution-modal-log-line">${line}</div>`
    ).join('');
  }
  
  // 2. 显示下载任务日志
  if (taskLogsResults && taskLogsResults.length > 0) {
    taskLogsResults.forEach(result => {
      if (result.logs.length > 0) {
        allLogsHtml += `<div class="execution-modal-log-section-title">📦 下载任务 #${result.taskId} (${result.albumCount}个本子)</div>`;
        allLogsHtml += result.logs.map(line => 
          `<div class="execution-modal-log-line">${line}</div>`
        ).join('');
      }
    });
  }
  
  if (allLogsHtml === '') {
    return '<div style="color: #9ca3af; text-align: center; padding: 20px;">暂无日志</div>';
  }
  
  return allLogsHtml;
}

/**
 * 渲染分页控制器
 */
export function renderPagination(taskId, currentPage, totalPages, totalCount) {
  if (totalPages <= 1) return '';
  
  return `
    <div class="executions-pagination">
      <button 
        class="pagination-arrow-btn ${currentPage === 1 ? 'disabled' : ''}" 
        data-action="exec-prev-page" 
        data-task-id="${taskId}"
        ${currentPage === 1 ? 'disabled' : ''}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <span class="pagination-page-info">第 ${currentPage} 页 / 共 ${totalPages} 页</span>
      <button 
        class="pagination-arrow-btn ${currentPage === totalPages ? 'disabled' : ''}" 
        data-action="exec-next-page" 
        data-task-id="${taskId}"
        ${currentPage === totalPages ? 'disabled' : ''}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </button>
    </div>`;
}

