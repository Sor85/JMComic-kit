/**
 * 执行历史管理模块
 * 
 * 负责加载和显示任务执行历史、执行详情和日志
 */
import * as api from './task-api.js';
import { renderTaskCard } from './ui-renderer.js';

// 展开的执行历史任务ID集合
let expandedExecutions = new Set();

// 执行记录缓存
let executionsCache = {};

// 分页状态：{ taskId: currentPage }
let paginationState = {};

/**
 * 加载所有自动化任务及其执行历史
 */
export async function loadAutoTasks() {
  try {
    const tasks = await api.fetchAllTasks();
    window.autoTasksCache = tasks;
    
    const container = document.getElementById('autoTasksList');
    if (tasks.length === 0) {
      container.innerHTML = '<div class="empty-state">暂无自动化任务，点击"创建自动化任务"按钮创建第一个。</div>';
      return;
    }
    
    // 保存已展开的编辑表单
    const existingEditWrapper = document.querySelector('.auto-task-edit-wrapper');
    let savedEditForm = null;
    let editingTaskId = null;
    
    if (existingEditWrapper) {
      const editFormCard = existingEditWrapper.querySelector('.forward-form-card');
      const editForm = editFormCard?.querySelector('#autoForm');
      editingTaskId = editForm?.dataset.editingId;
      
      // 只有当表单已展开时才保存
      if (existingEditWrapper.classList.contains('expanded') && editingTaskId) {
        savedEditForm = existingEditWrapper.cloneNode(true);
      }
    }
    
    // 为每个任务加载执行历史（加载所有记录，前端分页）
    const tasksWithExecutions = await Promise.all(tasks.map(async task => {
      try {
        const executions = await api.fetchTaskExecutions(task.id, 100);  // 增加到100条，前端分页显示
        executionsCache[task.id] = executions;
        return { task, executions };
      } catch {
        executionsCache[task.id] = [];
        return { task, executions: [] };
      }
    }));
    
    // 渲染任务列表（禁用过渡效果防止悬停动画反复触发）
    container.classList.add('no-transitions');
    container.innerHTML = tasksWithExecutions.map(({ task, executions }) => {
      const isExpanded = expandedExecutions.has(task.id);
      const currentPage = paginationState[task.id] || 1;
      return renderTaskCard(task, executions, isExpanded, currentPage);
    }).join('');
    
    // 双重 requestAnimationFrame 确保 DOM 完全更新后再启用过渡
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        container.classList.remove('no-transitions');
      });
    });
    
    // 备用清理，防止 requestAnimationFrame 未触发
    setTimeout(() => {
      container.classList.remove('no-transitions');
    }, 250);
    
    // 恢复编辑表单（在 no-transitions 清除后执行，避免触发展开动画）
    if (savedEditForm && editingTaskId) {
      setTimeout(() => {
        const targetCard = document.querySelector(`[data-action="auto-edit"][data-task-id="${editingTaskId}"]`)?.closest('.auto-task-card');
        if (targetCard) {
          // 克隆保存的表单
          const newWrapper = savedEditForm.cloneNode(true);
          
          // 确保expanded类存在
          if (!newWrapper.classList.contains('expanded')) {
            newWrapper.classList.add('expanded');
          }
          
          // 临时禁用过渡效果
          newWrapper.classList.add('no-transitions');
          
          // 插入到目标卡片
          targetCard.appendChild(newWrapper);
          
          // 立即移除禁用，因为表单已经是展开状态
          requestAnimationFrame(() => {
            newWrapper.classList.remove('no-transitions');
            // 重新绑定事件
            rebindEditFormEvents(newWrapper);
          });
        }
      }, 300);  // 稍微延迟，确保任务列表的 no-transitions 已清除
    }
    
  } catch (error) {
    console.error('加载自动化任务失败:', error);
  }
}

/**
 * 重新绑定编辑表单事件（占位函数，将从task-crud.js导出）
 */
function rebindEditFormEvents(wrapper) {
  // 这个函数将在task-crud.js中实现并导出
  // 这里只是占位，确保代码结构完整
  if (window.rebindEditFormEventsHandler) {
    window.rebindEditFormEventsHandler(wrapper);
  }
}

/**
 * 切换执行历史展开/收起
 */
export function toggleExecutions(taskId) {
  if (expandedExecutions.has(taskId)) {
    expandedExecutions.delete(taskId);
  } else {
    expandedExecutions.add(taskId);
  }
  
  const list = document.getElementById(`executions-list-${taskId}`);
  const icon = document.querySelector(`[data-action="toggle-executions"][data-task-id="${taskId}"] .toggle-icon`);
  
  if (list && icon) {
    list.classList.toggle('expanded');
    icon.classList.toggle('expanded');
  }
}

/**
 * 获取执行历史缓存
 */
export function getExecutionsCache() {
  return executionsCache;
}

/**
 * 获取展开状态集合
 */
export function getExpandedExecutions() {
  return expandedExecutions;
}

/**
 * 获取分页状态
 */
export function getPaginationState() {
  return paginationState;
}

/**
 * 切换到指定页
 */
export function goToPage(taskId, page) {
  const executions = executionsCache[taskId] || [];
  const totalPages = Math.ceil(executions.length / 10);
  
  // 确保页码在有效范围内
  if (page < 1) page = 1;
  if (page > totalPages) page = totalPages;
  
  paginationState[taskId] = page;
  
  // 重新渲染该任务的执行历史
  renderExecutionsList(taskId);
}

/**
 * 重新渲染单个任务的执行历史列表
 */
function renderExecutionsList(taskId) {
  const listElement = document.getElementById(`executions-list-${taskId}`);
  if (!listElement) return;
  
  const executions = executionsCache[taskId] || [];
  const currentPage = paginationState[taskId] || 1;
  const pageSize = 10;
  const totalPages = Math.ceil(executions.length / pageSize);
  
  // 计算当前页的执行记录
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const pageExecutions = executions.slice(startIndex, endIndex);
  
  // 动态导入 ui-renderer 中的函数
  import('./ui-renderer.js').then(({ renderExecutionsList, renderPagination }) => {
    const executionsHtml = renderExecutionsList(pageExecutions);
    const paginationHtml = renderPagination(taskId, currentPage, totalPages, executions.length);
    
    listElement.innerHTML = executionsHtml + paginationHtml;
  });
}

