/**
 * 自动化任务 CRUD 操作
 * 
 * 处理任务的创建、编辑、删除、启动、停止等操作
 */
import * as api from './task-api.js';
import { showMessage, showConfirm, parseSpeedLimit } from '../utils.js';
import { updateCustomSelectText, createCustomSelect } from '../select.js';
import { loadAutoTasks } from './execution-manager.js';

/**
 * 初始化表单事件
 */
export function initFormEvents() {
  document.getElementById('btnCreateAutoTask')?.addEventListener('click', showCreateForm);
  document.getElementById('btnCloseAutoForm')?.addEventListener('click', hideForm);
  document.getElementById('btnCancelAutoForm')?.addEventListener('click', hideForm);
  document.getElementById('autoForm')?.addEventListener('submit', handleSubmit);
  document.getElementById('toggleAutoPwd')?.addEventListener('click', togglePasswordVisibility);
  
  // 压缩配置显示/隐藏
  const autoEnableCompression = document.getElementById('autoEnableCompression');
  const autoCompressionConfig = document.getElementById('autoCompressionConfig');
  if (autoEnableCompression && autoCompressionConfig) {
    autoEnableCompression.addEventListener('change', () => {
      autoCompressionConfig.style.display = autoEnableCompression.checked ? 'block' : 'none';
    });
  }
  
  // PDF配置显示/隐藏
  const autoEnablePdf = document.getElementById('autoEnablePdf');
  const autoPdfConfig = document.getElementById('autoPdfConfig');
  if (autoEnablePdf && autoPdfConfig) {
    autoEnablePdf.addEventListener('change', () => {
      autoPdfConfig.style.display = autoEnablePdf.checked ? 'block' : 'none';
    });
  }
}

/**
 * 显示创建表单
 */
function showCreateForm() {
  document.getElementById('autoFormCard').style.display = 'block';
  document.getElementById('autoForm').reset();
  document.getElementById('autoForm').dataset.editingId = '';
  document.querySelector('.form-header h3').textContent = '新建自动化任务';
  
  const pwd = document.getElementById('autoPassword');
  if (pwd) {
    pwd.setAttribute('required', '');
    pwd.placeholder = '';
  }
  
  const submitBtn = document.querySelector('#autoForm .btn.btn-primary');
  if (submitBtn) submitBtn.textContent = '创建任务';
}

/**
 * 隐藏表单
 */
async function hideForm() {
  // 查找动态插入的编辑表单
  const wrapper = document.querySelector('.auto-task-edit-wrapper');
  if (wrapper) {
    await collapseAndRemoveForm(wrapper);
  } else {
    // 兼容旧的隐藏方式（用于新建任务表单）
    document.getElementById('autoFormCard').style.display = 'none';
  }
}

/**
 * 收起并移除表单的辅助函数
 */
function collapseAndRemoveForm(wrapper) {
  return new Promise((resolve) => {
    // 移除 expanded 类触发收起动画
    wrapper.classList.remove('expanded');
    
    let isResolved = false;
    
    // 等待动画完成后移除元素
    // 注意：transitionend 会为每个属性触发，我们只需要响应一次
    const handleTransitionEnd = (e) => {
      // 只响应 max-height 属性的过渡结束（这是最后完成的动画）
      if (e.propertyName === 'max-height' && !isResolved) {
        isResolved = true;
        wrapper.removeEventListener('transitionend', handleTransitionEnd);
        wrapper.remove();
        resolve();
      }
    };
    
    wrapper.addEventListener('transitionend', handleTransitionEnd);
    
    // 防止事件未触发，设置超时（比动画时间稍长）
    setTimeout(() => {
      if (wrapper.parentNode && !isResolved) {
        isResolved = true;
        wrapper.removeEventListener('transitionend', handleTransitionEnd);
        wrapper.remove();
        resolve();
      }
    }, 600);  // 增加到600ms，确保500ms的动画有足够时间完成
  });
}

/**
 * 切换密码可见性
 */
function togglePasswordVisibility() {
  const pwd = document.getElementById('autoPassword');
  if (!pwd) return;
  
  const isPwd = pwd.getAttribute('type') === 'password';
  pwd.setAttribute('type', isPwd ? 'text' : 'password');
  
  const icon = document.getElementById('toggleAutoPwdIcon');
  if (icon) {
    if (isPwd) {
      icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
    } else {
      icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
    }
  }
}

/**
 * 处理表单提交
 */
async function handleSubmit(e) {
  e.preventDefault();
  
  // 获取表单元素（可能是原始表单或克隆表单）
  const form = e.target;
  const formContainer = form.closest('.forward-form-card') || form.closest('#autoFormCard');
  
  const getElement = (id) => formContainer.querySelector(`#${id}`);
  
  const editingId = form.dataset.editingId;
  const batchAlbumsCount = parseInt(getElement('autoBatchAlbumsCount').value, 10);
  const batchIntervalMinutes = parseInt(getElement('autoBatchIntervalMinutes').value, 10);
  
  const data = {
    name: getElement('autoName').value,
    username: getElement('autoUsername').value,
    password: getElement('autoPassword').value,
    cron: getElement('autoCron').value.trim(),
    download_dir: getElement('autoDownloadDir').value,
    speed_limit: parseSpeedLimit(getElement('autoDownloadSpeed').value),
    client_impl: getElement('autoClientImpl').value,
    image_suffix: getElement('autoImageSuffix').value,
    dir_rule: getElement('autoDirRule').value.trim() || 'Aauthoroname/Pindextitle',
    batch_albums_count: (batchAlbumsCount > 0 && batchAlbumsCount <= 500) ? batchAlbumsCount : 50,
    batch_interval_minutes: (batchIntervalMinutes > 0 && batchIntervalMinutes <= 1440) ? batchIntervalMinutes : 30,
    run_now: getElement('autoRunNow').checked
  };

  // 添加压缩配置
  const autoEnableCompression = getElement('autoEnableCompression');
  if (autoEnableCompression && autoEnableCompression.checked) {
    const compressionPassword = getElement('autoCompressionPassword').value;
    data.compression = {
      enabled: true,
      format: getElement('autoCompressionFormat').value,
      level: getElement('autoCompressionLevel').value,
      password: compressionPassword || null,
      delete_original: getElement('autoDeleteAfterCompress').checked
    };
  } else {
    data.compression = { enabled: false };
  }
  
  // 添加PDF配置
  const autoEnablePdf = getElement('autoEnablePdf');
  if (autoEnablePdf && autoEnablePdf.checked) {
    const pdfPassword = getElement('autoPdfPassword').value;
    data.pdf = {
      enabled: true,
      level: getElement('autoPdfLevel').value,
      password: pdfPassword || null,
      delete_original: getElement('autoDeleteAfterPdf').checked
    };
  } else {
    data.pdf = { enabled: false };
  }
  
  // 验证 Cron 表达式
  const cronParts = data.cron.split(/\s+/);
  if (cronParts.length !== 5) {
    showMessage('Cron 表达式格式错误，应为5个字段，例如: 0 */6 * * *', 'error');
    return;
  }
  
  try {
    let result;
    if (editingId) {
      const response = await api.updateTask(editingId, data);
      if (response.error) {
        showMessage(`更新失败: ${response.error}`, 'error');
        return;
      }
      result = response;
    } else {
      const response = await api.createTask(data);
      if (response.error) {
        showMessage(`创建失败: ${response.error}`, 'error');
        return;
      }
      result = response;
    }
    
    // 等待表单完全隐藏后再刷新
    await hideForm();
    
    // 清理原始表单的编辑ID
    const originalForm = document.getElementById('autoForm');
    if (originalForm) {
      originalForm.dataset.editingId = '';
    }
    
    // 刷新任务列表
    await loadAutoTasks();
    
  } catch (error) {
    showMessage(`请求失败: ${error.message}`, 'error');
  }
}

/**
 * 编辑任务
 */
export async function editTask(id) {
  try {
    // 1. 找到目标任务卡片
    const taskCard = document.querySelector(`[data-action="auto-edit"][data-task-id="${id}"]`)?.closest('.auto-task-card');
    if (!taskCard) {
      showMessage('找不到任务卡片', 'error');
      return;
    }
    
    // 2. 检查当前任务是否已经展开了编辑表单
    const existingWrapper = taskCard.querySelector('.auto-task-edit-wrapper');
    
    // 如果当前任务已经展开编辑表单，则折叠它（切换功能）
    if (existingWrapper) {
      await collapseAndRemoveForm(existingWrapper);
      return;
    }
    
    // 3. 关闭其他任务的编辑表单
    const otherWrapper = document.querySelector('.auto-task-edit-wrapper');
    if (otherWrapper) {
      await collapseAndRemoveForm(otherWrapper);
    }
    
    // 4. 加载任务详情
    const task = await api.fetchTaskDetail(id, true);
    
    if (!task || task.error) {
      showMessage('加载任务失败', 'error');
      return;
    }
    
    // 5. 克隆表单模板
    const formTemplate = document.getElementById('autoFormCard');
    const formClone = formTemplate.cloneNode(true);
    formClone.removeAttribute('id');
    formClone.classList.add('cloned-form-card');
    formClone.style.display = 'block';
    
    // 5.5. 处理克隆表单中的自定义下拉菜单
    // 移除克隆的 custom-select-wrapper，恢复原始 select 元素
    const clonedWrappers = formClone.querySelectorAll('.custom-select-wrapper');
    console.log(`[编辑表单] 找到 ${clonedWrappers.length} 个克隆的 custom-select-wrapper`);
    clonedWrappers.forEach(wrapper => {
      const select = wrapper.querySelector('select');
      if (select) {
        console.log(`[编辑表单] 恢复 select: ${select.id || '(无ID)'}`);
        // 将 select 移到 wrapper 的位置
        wrapper.parentNode.insertBefore(select, wrapper);
        wrapper.remove();
      }
    });
    
    // 6. 创建包装器并插入
    const wrapper = document.createElement('div');
    wrapper.className = 'auto-task-edit-wrapper';
    wrapper.appendChild(formClone);
    taskCard.appendChild(wrapper);
    
    // 7. 绑定克隆表单的事件（包括重新初始化下拉菜单）
    bindClonedFormEvents(formClone);
    
    // 8. 填充表单数据
    fillFormData(formClone, task, id);
    
    // 9. 触发展开动画
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        wrapper.classList.add('expanded');
      });
    });
    
  } catch (error) {
    showMessage('加载任务失败', 'error');
  }
}

/**
 * 绑定克隆表单的事件
 */
function bindClonedFormEvents(formClone) {
  // 重新初始化克隆表单中的自定义下拉菜单
  const selects = formClone.querySelectorAll('select');
  console.log(`[编辑表单] 找到 ${selects.length} 个 select 元素需要初始化`);
  selects.forEach((select, index) => {
    console.log(`[编辑表单] 正在初始化第 ${index + 1} 个 select: ${select.id || '(无ID)'}`);
    createCustomSelect(select);
  });
  
  // 绑定关闭按钮
  const closeBtn = formClone.querySelector('.icon-close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', hideForm);
  }
  
  // 绑定取消按钮
  const cancelBtn = formClone.querySelector('#btnCancelAutoForm');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', hideForm);
  }
  
  // 绑定表单提交
  const form = formClone.querySelector('#autoForm');
  if (form) {
    form.addEventListener('submit', handleSubmit);
  }
  
  // 绑定密码显示/隐藏
  const togglePwdBtn = formClone.querySelector('#toggleAutoPwd');
  if (togglePwdBtn) {
    togglePwdBtn.addEventListener('click', function() {
      const pwd = formClone.querySelector('#autoPassword');
      if (!pwd) return;
      
      const isPwd = pwd.getAttribute('type') === 'password';
      pwd.setAttribute('type', isPwd ? 'text' : 'password');
      
      const icon = formClone.querySelector('#toggleAutoPwdIcon');
      if (icon) {
        if (isPwd) {
          icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
        } else {
          icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
        }
      }
    });
  }
  
  // 绑定压缩配置显示/隐藏
  const enableCompression = formClone.querySelector('#autoEnableCompression');
  const compressionConfig = formClone.querySelector('#autoCompressionConfig');
  if (enableCompression && compressionConfig) {
    enableCompression.addEventListener('change', () => {
      compressionConfig.style.display = enableCompression.checked ? 'block' : 'none';
    });
  }
  
  // 绑定PDF配置显示/隐藏
  const enablePdf = formClone.querySelector('#autoEnablePdf');
  const pdfConfig = formClone.querySelector('#autoPdfConfig');
  if (enablePdf && pdfConfig) {
    enablePdf.addEventListener('change', () => {
      pdfConfig.style.display = enablePdf.checked ? 'block' : 'none';
    });
  }
}

/**
 * 重新绑定恢复的编辑表单的事件
 * 用于在 loadAutoTasks 重新渲染后恢复编辑表单时使用
 */
export function rebindRestoredEditForm(wrapper) {
  const formClone = wrapper.querySelector('.forward-form-card');
  if (formClone) {
    // 先移除旧的 custom-select-wrapper
    const oldWrappers = formClone.querySelectorAll('.custom-select-wrapper');
    oldWrappers.forEach(oldWrapper => {
      const select = oldWrapper.querySelector('select');
      if (select) {
        oldWrapper.parentNode.insertBefore(select, oldWrapper);
        oldWrapper.remove();
      }
    });
    
    // bindClonedFormEvents 会重新初始化下拉菜单
    bindClonedFormEvents(formClone);
  }
}

// 将函数注册到 window 对象供 execution-manager.js 使用
if (typeof window !== 'undefined') {
  window.rebindEditFormEventsHandler = rebindRestoredEditForm;
}

/**
 * 填充表单数据
 */
function fillFormData(formClone, task, id) {
  // 基本信息
  formClone.querySelector('#autoName').value = task.name;
  formClone.querySelector('#autoUsername').value = task.username;
  
  const pwd = formClone.querySelector('#autoPassword');
  if (pwd) {
    pwd.value = task.password || '';
    pwd.removeAttribute('required');
    pwd.setAttribute('type', 'password');
  }
  
  const icon = formClone.querySelector('#toggleAutoPwdIcon');
  if (icon) {
    icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
  }
  
  formClone.querySelector('#autoCron').value = task.cron;
  formClone.querySelector('#autoDownloadDir').value = task.download_dir;
  
  const speedValue = task.speed_limit > 0 
    ? (task.speed_limit >= 1024 && task.speed_limit % 1024 === 0 
       ? `${task.speed_limit / 1024}mb` 
       : `${task.speed_limit}kb`)
    : '';
  formClone.querySelector('#autoDownloadSpeed').value = speedValue;
  
  formClone.querySelector('#autoClientImpl').value = task.client_impl;
  formClone.querySelector('#autoImageSuffix').value = task.image_suffix || '';
  formClone.querySelector('#autoDirRule').value = task.dir_rule || 'Aauthoroname/Pindextitle';
  
  // 兼容旧数据
  formClone.querySelector('#autoBatchAlbumsCount').value = task.batch_albums_count || task.batch_size || 50;
  formClone.querySelector('#autoBatchIntervalMinutes').value = task.batch_interval_minutes || 30;
  
  // 回填压缩配置
  const compression = task.compression || {};
  const autoEnableCompression = formClone.querySelector('#autoEnableCompression');
  const autoCompressionConfig = formClone.querySelector('#autoCompressionConfig');
  if (compression.enabled) {
    autoEnableCompression.checked = true;
    autoCompressionConfig.style.display = 'block';
    formClone.querySelector('#autoCompressionFormat').value = compression.format || 'zip';
    formClone.querySelector('#autoCompressionLevel').value = compression.level || 'album';
    formClone.querySelector('#autoCompressionPassword').value = '';
    formClone.querySelector('#autoDeleteAfterCompress').checked = compression.delete_original || false;
  } else {
    autoEnableCompression.checked = false;
    autoCompressionConfig.style.display = 'none';
  }
  
  // 回填PDF配置
  const pdf = task.pdf || {};
  const autoEnablePdf = formClone.querySelector('#autoEnablePdf');
  const autoPdfConfig = formClone.querySelector('#autoPdfConfig');
  if (pdf.enabled) {
    autoEnablePdf.checked = true;
    autoPdfConfig.style.display = 'block';
    formClone.querySelector('#autoPdfLevel').value = pdf.level || 'album';
    formClone.querySelector('#autoPdfPassword').value = '';
    formClone.querySelector('#autoDeleteAfterPdf').checked = pdf.delete_original || false;
  } else {
    autoEnablePdf.checked = false;
    autoPdfConfig.style.display = 'none';
  }
  
  formClone.querySelector('#autoRunNow').checked = false;
  
  updateCustomSelectText(formClone.querySelector('#autoClientImpl'));
  updateCustomSelectText(formClone.querySelector('#autoImageSuffix'));
  
  formClone.querySelector('.form-header h3').textContent = '编辑自动化任务';
  formClone.querySelector('#autoForm').dataset.editingId = id;
  
  const submitBtn = formClone.querySelector('#autoForm .btn.btn-primary');
  if (submitBtn) submitBtn.textContent = '保存修改';
}

/**
 * 启动任务
 */
export async function startTask(id) {
  try {
    const result = await api.startTask(id);
    if (result.error) {
      showMessage(`启动失败: ${result.error}`, 'error');
    } else {
      await loadAutoTasks();
    }
  } catch (error) {
    showMessage(`请求失败: ${error.message}`, 'error');
  }
}

/**
 * 停止任务
 */
export async function stopTask(id) {
  try {
    const result = await api.stopTask(id);
    if (result.error) {
      showMessage(`停止失败: ${result.error}`, 'error');
    } else {
      await loadAutoTasks();
    }
  } catch (error) {
    showMessage(`请求失败: ${error.message}`, 'error');
  }
}

/**
 * 立即执行任务
 */
export async function runTaskNow(id) {
  const confirmed = await showConfirm('确定要立即执行此任务吗？');
  if (!confirmed) return;
  
  try {
    const result = await api.runTaskNow(id);
    if (result.error) {
      showMessage(`执行失败: ${result.error}`, 'error');
    } else {
      // 立即更新对应卡片的状态为运行中
      const card = document.querySelector(`.auto-task-card [data-action="auto-start"][data-task-id="${id}"]`)?.closest('.auto-task-card')
        || document.querySelector(`.auto-task-card .icon-stop-btn[data-task-id="${id}"]`)?.closest('.auto-task-card');
      
      if (card) {
        card.classList.remove('stopped');
        card.classList.add('running');
        const badge = card.querySelector('.status-badge');
        if (badge) {
          badge.textContent = '运行中';
          badge.classList.remove('stopped');
          badge.classList.add('running');
        }
      }
      
      // 短延迟后刷新一次
      setTimeout(() => loadAutoTasks(), 1000);
    }
  } catch (error) {
    showMessage(`请求失败: ${error.message}`, 'error');
  }
}

/**
 * 删除任务
 */
export async function deleteTask(id) {
  const confirmed = await showConfirm('确定要删除此自动化任务吗？');
  if (!confirmed) return;
  
  try {
    const result = await api.deleteTask(id);
    if (result.error) {
      showMessage(`删除失败: ${result.error}`, 'error');
    } else {
      showMessage('任务已删除', 'success');
      await loadAutoTasks();
    }
  } catch (error) {
    showMessage(`请求失败: ${error.message}`, 'error');
  }
}

/**
 * 删除执行记录
 */
export async function deleteExecution(executionId, taskId) {
  const confirmed = await showConfirm('确定要删除这条执行记录吗？');
  if (!confirmed) return;
  
  try {
    const result = await api.deleteExecution(executionId);
    if (result.error) {
      showMessage(`删除失败: ${result.error}`, 'error');
    } else {
      await loadAutoTasks();
    }
  } catch (error) {
    showMessage(`请求失败: ${error.message}`, 'error');
  }
}

