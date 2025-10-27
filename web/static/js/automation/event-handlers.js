/**
 * 事件处理器
 * 
 * 统一管理所有自动化任务相关的事件监听
 */
import { editTask, startTask, stopTask, runTaskNow, deleteTask, deleteExecution } from './task-crud.js';
import { toggleExecutions, goToPage, getPaginationState } from './execution-manager.js';
import { showExecutionDetail } from './modal-handler.js';

/**
 * 初始化全局事件监听
 */
export function initEventHandlers() {
  // 使用事件委托处理所有点击事件
  document.addEventListener('click', handleGlobalClick);
}

/**
 * 全局点击事件处理
 */
async function handleGlobalClick(e) {
  // 处理删除执行记录按钮（优先处理，避免冒泡）
  const deleteExecBtn = e.target.closest('[data-action="delete-execution"]');
  if (deleteExecBtn) {
    e.stopPropagation();
    const executionId = parseInt(deleteExecBtn.dataset.executionId, 10);
    const taskId = parseInt(deleteExecBtn.dataset.taskId, 10);
    await deleteExecution(executionId, taskId);
    return;
  }
  
  // 处理分页按钮（上一页）
  const prevPageBtn = e.target.closest('[data-action="exec-prev-page"]');
  if (prevPageBtn) {
    e.stopPropagation();
    const taskId = parseInt(prevPageBtn.dataset.taskId, 10);
    const currentPage = getPaginationState()[taskId] || 1;
    goToPage(taskId, currentPage - 1);
    return;
  }
  
  // 处理分页按钮（下一页）
  const nextPageBtn = e.target.closest('[data-action="exec-next-page"]');
  if (nextPageBtn) {
    e.stopPropagation();
    const taskId = parseInt(nextPageBtn.dataset.taskId, 10);
    const currentPage = getPaginationState()[taskId] || 1;
    goToPage(taskId, currentPage + 1);
    return;
  }
  
  // 处理自动化任务操作按钮
  const btn = e.target.closest('[data-action][data-task-id]');
  if (btn) {
    const id = parseInt(btn.dataset.taskId, 10);
    await handleTaskAction(btn.dataset.action, id);
    return;
  }
  
  // 处理执行详情查看
  const execBtn = e.target.closest('[data-action="view-execution"]');
  if (execBtn) {
    const executionId = parseInt(execBtn.dataset.executionId, 10);
    await showExecutionDetail(executionId);
    return;
  }
}

/**
 * 处理任务操作
 */
async function handleTaskAction(action, taskId) {
  switch (action) {
    case 'auto-start':
      await startTask(taskId);
      break;
    case 'auto-stop':
      await stopTask(taskId);
      break;
    case 'auto-run':
      await runTaskNow(taskId);
      break;
    case 'auto-edit':
      await editTask(taskId);
      break;
    case 'auto-delete':
      await deleteTask(taskId);
      break;
    case 'toggle-executions':
      toggleExecutions(taskId);
      break;
  }
}

