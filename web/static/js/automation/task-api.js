/**
 * 自动化任务 API 调用封装
 * 
 * 提供与后端交互的所有 API 函数
 */
import { API_BASE } from '../config.js';

/**
 * 获取所有自动化任务
 */
export async function fetchAllTasks() {
  const response = await fetch(`${API_BASE}/api/automation`);
  return await response.json();
}

/**
 * 获取单个任务详情（包含敏感信息）
 */
export async function fetchTaskDetail(taskId, includeSensitive = false) {
  const url = includeSensitive 
    ? `${API_BASE}/api/automation/${taskId}?include_sensitive=1`
    : `${API_BASE}/api/automation/${taskId}`;
  const response = await fetch(url);
  return await response.json();
}

/**
 * 创建自动化任务
 */
export async function createTask(taskData) {
  const response = await fetch(`${API_BASE}/api/automation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData)
  });
  return await response.json();
}

/**
 * 更新自动化任务
 */
export async function updateTask(taskId, taskData) {
  const response = await fetch(`${API_BASE}/api/automation/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData)
  });
  return await response.json();
}

/**
 * 删除自动化任务
 */
export async function deleteTask(taskId) {
  const response = await fetch(`${API_BASE}/api/automation/${taskId}`, {
    method: 'DELETE'
  });
  return await response.json();
}

/**
 * 启动自动化任务
 */
export async function startTask(taskId) {
  const response = await fetch(`${API_BASE}/api/automation/${taskId}/start`, {
    method: 'POST'
  });
  return await response.json();
}

/**
 * 停止自动化任务
 */
export async function stopTask(taskId) {
  const response = await fetch(`${API_BASE}/api/automation/${taskId}/stop`, {
    method: 'POST'
  });
  return await response.json();
}

/**
 * 立即执行自动化任务
 */
export async function runTaskNow(taskId) {
  const response = await fetch(`${API_BASE}/api/automation/${taskId}/run`, {
    method: 'POST'
  });
  return await response.json();
}

/**
 * 获取任务执行历史
 */
export async function fetchTaskExecutions(taskId, limit = 5) {
  const response = await fetch(`${API_BASE}/api/automation/${taskId}/executions?limit=${limit}`);
  return await response.json();
}

/**
 * 获取执行详情（包含关联任务）
 */
export async function fetchExecutionDetail(executionId) {
  const response = await fetch(`${API_BASE}/api/automation/execution/${executionId}`);
  return await response.json();
}

/**
 * 获取执行日志
 */
export async function fetchExecutionLogs(executionId, limit = 500) {
  const response = await fetch(`${API_BASE}/api/automation/execution/${executionId}/logs?limit=${limit}`);
  return await response.json();
}

/**
 * 获取下载任务的实时日志
 */
export async function fetchTaskLogs(taskId) {
  const response = await fetch(`${API_BASE}/api/realtime_logs/${taskId}`);
  return await response.json();
}

/**
 * 重试下载任务中失败的图片
 */
export async function retryTaskFailedImages(taskId) {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}/retry`, {
    method: 'POST'
  });
  return await response.json();
}

/**
 * 删除执行记录
 */
export async function deleteExecution(executionId) {
  const response = await fetch(`${API_BASE}/api/automation/execution/${executionId}`, {
    method: 'DELETE'
  });
  return await response.json();
}

