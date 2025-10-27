/**
 * 执行详情模态框处理
 * 
 * 负责显示和更新执行详情模态框，包括统计信息、日志和关联任务
 */
import * as api from './task-api.js';
import { renderExecutionStats, renderRelatedTasks, renderExecutionLogs } from './ui-renderer.js';
import { showMessage } from '../utils.js';

// 当前打开的执行详情模态框ID
let currentExecutionModalId = null;

// 实时日志轮询定时器
let executionLogsPollingInterval = null;

/**
 * 显示执行详情模态框
 */
export async function showExecutionDetail(executionId) {
  currentExecutionModalId = executionId;
  
  const modal = document.getElementById('executionDetailModal');
  modal.style.display = 'flex';
  
  // 显示加载状态
  document.getElementById('executionModalStats').innerHTML = '<div style="color: #9ca3af; text-align: center; padding: 20px;">加载中...</div>';
  document.getElementById('executionModalLogs').innerHTML = '<div style="color: #9ca3af; text-align: center; padding: 20px;">加载中...</div>';
  document.getElementById('executionModalTasksSection').style.display = 'none';
  
  try {
    const data = await api.fetchExecutionDetail(executionId);
    const execution = data.execution;
    const relatedTasks = data.related_tasks;
    
    // 更新标题
    document.getElementById('executionModalTitle').textContent = `执行详情 #${execution.id} - ${execution.auto_task_name}`;
    
    // 更新统计信息
    document.getElementById('executionModalStats').innerHTML = renderExecutionStats(execution);
    
    // 加载日志
    await loadExecutionLogs(executionId);
    
    // 显示关联任务
    if (relatedTasks && relatedTasks.length > 0) {
      document.getElementById('executionModalTasksSection').style.display = 'block';
      document.getElementById('executionModalTasks').innerHTML = renderRelatedTasks(relatedTasks);
    }
    
    // 如果是运行中的任务，启动实时刷新
    if (execution.status === 'running') {
      startExecutionLogsPolling(executionId);
    }
    
  } catch (error) {
    document.getElementById('executionModalStats').innerHTML = `<div style="color: #ef4444; text-align: center; padding: 20px;">加载失败: ${error.message}</div>`;
  }
}

/**
 * 加载执行日志（包含自动化同步日志和关联下载任务的日志）
 */
async function loadExecutionLogs(executionId) {
  try {
    // 获取执行记录详情（包含关联任务）
    const detailData = await api.fetchExecutionDetail(executionId);
    const execution = detailData.execution;
    const relatedTasks = detailData.related_tasks || [];
    
    // 更新关联任务状态显示（重要：实时更新任务状态）
    if (relatedTasks && relatedTasks.length > 0) {
      const tasksSection = document.getElementById('executionModalTasksSection');
      const tasksContainer = document.getElementById('executionModalTasks');
      if (tasksSection && tasksContainer) {
        tasksSection.style.display = 'block';
        tasksContainer.innerHTML = renderRelatedTasks(relatedTasks);
      }
    }
    
    // 获取自动化同步阶段的日志
    const syncLogs = await api.fetchExecutionLogs(executionId, 500);
    
    // 获取所有关联下载任务的日志
    const taskLogsResults = await Promise.all(relatedTasks.map(async task => {
      try {
        const taskLogs = await api.fetchTaskLogs(task.id);
        return {
          taskId: task.id,
          albumCount: task.album_ids?.length || 0,
          logs: taskLogs
        };
      } catch {
        return { taskId: task.id, albumCount: 0, logs: [] };
      }
    }));
    
    // 渲染所有日志
    const logsContainer = document.getElementById('executionModalLogs');
    logsContainer.innerHTML = renderExecutionLogs(syncLogs, taskLogsResults);
    
    // 滚动到底部
    logsContainer.scrollTop = logsContainer.scrollHeight;
    
  } catch (error) {
    document.getElementById('executionModalLogs').innerHTML = `<div style="color: #ef4444; text-align: center; padding: 20px;">加载日志失败: ${error.message}</div>`;
  }
}

/**
 * 启动实时日志轮询
 */
function startExecutionLogsPolling(executionId) {
  stopExecutionLogsPolling();
  executionLogsPollingInterval = setInterval(() => {
    if (currentExecutionModalId === executionId) {
      loadExecutionLogs(executionId);
    } else {
      stopExecutionLogsPolling();
    }
  }, 2000);
}

/**
 * 停止实时日志轮询
 */
function stopExecutionLogsPolling() {
  if (executionLogsPollingInterval) {
    clearInterval(executionLogsPollingInterval);
    executionLogsPollingInterval = null;
  }
}

/**
 * 关闭执行详情模态框
 */
export function closeExecutionModal() {
  document.getElementById('executionDetailModal').style.display = 'none';
  currentExecutionModalId = null;
  stopExecutionLogsPolling();
}

/**
 * 初始化模态框事件
 */
export function initModalEvents() {
  document.getElementById('closeExecutionModal')?.addEventListener('click', closeExecutionModal);
  document.querySelector('.execution-modal-overlay')?.addEventListener('click', closeExecutionModal);
  
  // 使用事件委托处理重试按钮点击
  document.getElementById('executionModalTasks')?.addEventListener('click', handleRetryButtonClick);
}

/**
 * 处理重试按钮点击
 */
async function handleRetryButtonClick(e) {
  const btn = e.target.closest('.btn-retry-failed');
  if (!btn) return;
  
  const taskId = parseInt(btn.dataset.taskId, 10);
  if (!taskId) return;
  
  // 禁用按钮，显示加载状态
  btn.disabled = true;
  const originalText = btn.innerHTML;
  btn.innerHTML = '<span style="opacity: 0.6;">重试中...</span>';
  
  try {
    const result = await api.retryTaskFailedImages(taskId);
    
    if (result.error) {
      showMessage(`重试失败: ${result.error}`, 'error');
    } else {
      showMessage('已开始重试失败的图片，请查看日志', 'success');
      
      // 1秒后刷新执行详情
      setTimeout(() => {
        if (currentExecutionModalId) {
          loadExecutionLogs(currentExecutionModalId);
        }
      }, 1000);
    }
  } catch (error) {
    showMessage(`请求失败: ${error.message}`, 'error');
  } finally {
    // 恢复按钮状态
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }, 2000);
  }
}

/**
 * 获取当前模态框ID
 */
export function getCurrentExecutionModalId() {
  return currentExecutionModalId;
}

