/**
 * 自动化任务模块主入口
 * 
 * 整合所有子模块，提供统一的初始化接口
 */
import { initFormEvents } from './task-crud.js';
import { loadAutoTasks } from './execution-manager.js';
import { initModalEvents } from './modal-handler.js';
import { initEventHandlers } from './event-handlers.js';

/**
 * 初始化自动化模块
 * 
 * 在页面加载时调用，初始化所有事件监听器
 */
export function initAutomation() {
  initFormEvents();
  initModalEvents();
  initEventHandlers();
}

/**
 * 导出加载函数供外部使用
 */
export { loadAutoTasks };

