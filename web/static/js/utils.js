// 工具函数（从 app.js 抽取）

export function showLoading() {
  document.getElementById('loadingOverlay').style.display = 'flex';
}

export function hideLoading() {
  document.getElementById('loadingOverlay').style.display = 'none';
}

export function showMessage(message, type = 'info') {
  return new Promise((resolve) => {
    const modal = document.getElementById('messageModal');
    const text = modal.querySelector('.message-modal-text');
    const confirmBtn = modal.querySelector('.message-modal-btn-confirm');
    const cancelBtn = modal.querySelector('.message-modal-btn-cancel');
    
    // 设置内容和类型
    text.textContent = message;
    modal.className = `message-modal show ${type}`;
    
    // 只显示确定按钮
    confirmBtn.style.display = 'inline-block';
    cancelBtn.style.display = 'none';
    
    // 确定按钮事件
    const handleConfirm = () => {
      modal.classList.remove('show');
      confirmBtn.removeEventListener('click', handleConfirm);
      resolve(true);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    
    // 点击背景关闭
    const handleBackdrop = (e) => {
      if (e.target === modal) {
        modal.classList.remove('show');
        modal.removeEventListener('click', handleBackdrop);
        resolve(true);
      }
    };
    modal.addEventListener('click', handleBackdrop);
  });
}

export function showConfirm(message) {
  return new Promise((resolve) => {
    const modal = document.getElementById('messageModal');
    const text = modal.querySelector('.message-modal-text');
    const confirmBtn = modal.querySelector('.message-modal-btn-confirm');
    const cancelBtn = modal.querySelector('.message-modal-btn-cancel');
    
    // 设置内容
    text.textContent = message;
    modal.className = 'message-modal show warning';
    
    // 显示两个按钮
    confirmBtn.style.display = 'inline-block';
    cancelBtn.style.display = 'inline-block';
    
    // 确定按钮事件
    const handleConfirm = () => {
      modal.classList.remove('show');
      cleanup();
      resolve(true);
    };
    
    // 取消按钮事件
    const handleCancel = () => {
      modal.classList.remove('show');
      cleanup();
      resolve(false);
    };
    
    const cleanup = () => {
      confirmBtn.removeEventListener('click', handleConfirm);
      cancelBtn.removeEventListener('click', handleCancel);
    };
    
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
  });
}

export function parseIds(text) {
  return text.trim().split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#'))
    .map(line => line.replace(/JM|jm/g, ''))
    .filter(line => /^\d+$/.test(line));
}

export function formatTime(isoString) {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return date.toLocaleString('zh-CN');
}

export function formatDuration(start, end) {
  if (!start || !end) return '-';
  const startTime = new Date(start);
  const endTime = new Date(end);
  const duration = (endTime - startTime) / 1000; // 秒
  
  if (duration < 60) return `${duration.toFixed(1)}秒`;
  if (duration < 3600) return `${(duration / 60).toFixed(1)}分钟`;
  return `${(duration / 3600).toFixed(1)}小时`;
}

export function parseSpeedLimit(input) {
  if (!input || input.trim() === '') return 0;
  
  const value = input.trim().toLowerCase();
  const match = value.match(/^(\d+(?:\.\d+)?)\s*(mb|kb)?$/);
  
  if (!match) return 0;
  
  const number = parseFloat(match[1]);
  const unit = match[2] || 'kb'; // 默认单位为 kb
  
  if (unit === 'mb') {
    return Math.floor(number * 1024); // 转换为 KB
  } else {
    return Math.floor(number); // 已经是 KB
  }
}

export function formatSpeedLimit(kb) {
  if (!kb || kb === 0) return '无限制';
  
  if (kb >= 1024 && kb % 1024 === 0) {
    return `${kb / 1024}MB`;
  }
  return `${kb}KB`;
}

// 不再暴露到全局，采用模块导入方式


