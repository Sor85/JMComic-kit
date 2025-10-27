/**
 * CSV 导入功能
 * 从导出的收藏夹CSV文件导入本子ID
 */

import { showMessage } from './utils.js';
import { refreshCustomSelect } from './select.js';

/**
 * 初始化CSV导入功能
 */
export function initCsvImport() {
  console.log('[CSV Import] 初始化CSV导入功能...');
  
  // 检查必要的DOM元素
  const selectElement = document.getElementById('csvFileSelect');
  const btnImportCsv = document.getElementById('btnImportCsv');
  
  if (!selectElement) {
    console.error('[CSV Import] 找不到csvFileSelect元素！');
    return;
  }
  
  if (!btnImportCsv) {
    console.error('[CSV Import] 找不到btnImportCsv按钮！');
    return;
  }
  
  console.log('[CSV Import] DOM元素检查通过，开始加载文件列表...');
  loadCsvFileList();
  
  // 绑定导入按钮点击事件
  btnImportCsv.addEventListener('click', handleImportClick);
  console.log('[CSV Import] 初始化完成');
}

/**
 * 加载CSV文件列表
 */
async function loadCsvFileList() {
  const selectElement = document.getElementById('csvFileSelect');
  if (!selectElement) {
    console.error('CSV文件选择框元素不存在');
    return;
  }
  
  try {
    console.log('正在加载CSV文件列表...');
    const response = await fetch('/api/csv/list');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const files = await response.json();
    console.log('CSV文件列表:', files);
    
    // 清空现有选项（保留第一个默认选项）
    selectElement.innerHTML = '<option value="">-- 选择CSV文件 --</option>';
    
    if (files && Array.isArray(files) && files.length > 0) {
      console.log(`找到 ${files.length} 个CSV文件`);
      files.forEach(file => {
        const option = document.createElement('option');
        option.value = file.filename;
        
        // 格式化显示：文件名 (大小, 修改时间)
        const sizeKB = (file.size / 1024).toFixed(1);
        const modifiedDate = new Date(file.modified).toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        });
        
        option.textContent = `${file.filename} (${sizeKB}KB, ${modifiedDate})`;
        selectElement.appendChild(option);
      });
      
      // 刷新自定义下拉框以显示新添加的选项
      console.log('刷新自定义下拉框...');
      refreshCustomSelect(selectElement);
    } else {
      // 没有CSV文件时显示提示
      console.log('没有找到CSV文件');
      const option = document.createElement('option');
      option.value = '';
      option.textContent = '-- 暂无导出的CSV文件，请先导出收藏夹 --';
      option.disabled = true;
      selectElement.appendChild(option);
      
      // 刷新自定义下拉框
      refreshCustomSelect(selectElement);
    }
  } catch (error) {
    console.error('加载CSV文件列表失败:', error);
    const option = document.createElement('option');
    option.value = '';
    option.textContent = `-- 加载失败: ${error.message} --`;
    option.disabled = true;
    selectElement.innerHTML = '<option value="">-- 选择CSV文件 --</option>';
    selectElement.appendChild(option);
    
    // 刷新自定义下拉框
    refreshCustomSelect(selectElement);
    showMessage('error', `加载CSV文件列表失败: ${error.message}`);
  }
}

/**
 * 处理导入按钮点击
 */
async function handleImportClick() {
  const selectElement = document.getElementById('csvFileSelect');
  const filename = selectElement?.value;
  
  if (!filename) {
    showMessage('warning', '请先选择一个CSV文件');
    return;
  }
  
  await importCsvFile(filename);
}

/**
 * 导入CSV文件中的本子ID
 * @param {string} filename - CSV文件名
 */
async function importCsvFile(filename) {
  const albumIdsTextarea = document.getElementById('albumIds');
  if (!albumIdsTextarea) return;
  
  try {
    // 显示加载提示
    const btnImportCsv = document.getElementById('btnImportCsv');
    const originalText = btnImportCsv?.textContent;
    if (btnImportCsv) {
      btnImportCsv.disabled = true;
      btnImportCsv.textContent = '导入中...';
    }
    
    // 调用后端API读取CSV
    const response = await fetch(`/api/csv/read/${encodeURIComponent(filename)}`);
    const data = await response.json();
    
    // 恢复按钮状态
    if (btnImportCsv) {
      btnImportCsv.disabled = false;
      btnImportCsv.textContent = originalText;
    }
    
    // 处理错误
    if (!response.ok || data.error) {
      showMessage('error', data.error || '导入失败');
      return;
    }
    
    // 检查是否有数据
    if (!data.ids || data.ids.length === 0) {
      showMessage('warning', data.message || 'CSV文件中没有找到本子ID');
      return;
    }
    
    // 填充到输入框
    albumIdsTextarea.value = data.ids.join('\n');
    
    // 显示成功提示
    showMessage('success', `成功导入 ${data.count} 个本子ID`);
    
    // 触发输入事件（如果有自动保存功能）
    albumIdsTextarea.dispatchEvent(new Event('input', { bubbles: true }));
    
  } catch (error) {
    console.error('导入CSV失败:', error);
    showMessage('error', `导入失败: ${error.message}`);
    
    // 恢复按钮状态
    const btnImportCsv = document.getElementById('btnImportCsv');
    if (btnImportCsv) {
      btnImportCsv.disabled = false;
      btnImportCsv.textContent = '导入';
    }
  }
}

/**
 * 刷新CSV文件列表（供外部调用）
 */
export function refreshCsvFileList() {
  loadCsvFileList();
}

