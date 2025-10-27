import { initCustomSelects } from './select.js';
import { initAutomation, loadAutoTasks } from './automation/index.js';
import { showMessage } from './utils.js';
import { loadManualLogs, applyManualFilters, loadLogs } from './logs.js';
import { initDownloadForm } from './download.js';
import { initExportForm } from './export.js';
import { initCsvImport } from './csv-import.js';

function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      tabContents.forEach(content => {
        if (content.dataset.content === tab) {
          content.classList.add('active');
          if (tab === 'manual') loadManualLogs();
          if (tab === 'automation') { loadAutoTasks(); }
        } else {
          content.classList.remove('active');
        }
      });
    });
  });
}

function initOperationSwitch() {
  const switchBtns = document.querySelectorAll('.switch-btn');
  const operationContents = document.querySelectorAll('.operation-content');
  switchBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const operation = btn.dataset.operation;
      switchBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      operationContents.forEach(content => {
        if (content.dataset.operationContent === operation) content.classList.add('active');
        else content.classList.remove('active');
      });
    });
  });
}

function initLogFilters() {
  document.getElementById('manualFilterLevel')?.addEventListener('change', applyManualFilters);
  document.getElementById('manualFilterTimeRange')?.addEventListener('change', applyManualFilters);
  document.getElementById('manualFilterKeyword')?.addEventListener('input', applyManualFilters);
  document.getElementById('refreshManualLogs')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget; btn.classList.add('refreshing');
    await loadManualLogs();
    setTimeout(() => btn.classList.remove('refreshing'), 600);
  });
}

function startAutoRefresh() {
  setInterval(async () => {
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab?.dataset.content === 'manual') {
      const list = document.getElementById('manualLogsList');
      const isHover = list?.matches(':hover');
      // 鼠标悬停时延迟刷新，避免 hover 动画被频繁中断
      if (isHover) return;
      // 如果有展开的任务，优先拉取这些任务的快照，保证它们的状态一致
      const expanded = Array.from(document.querySelectorAll('.task-detail-content.expanded'))
        .map(el => parseInt(el.id.replace('log-task-detail-',''), 10))
        .filter(id => !Number.isNaN(id));
      if (expanded.length === 0) {
        loadManualLogs();
        return;
      }
      // 轻量刷新：触发 logs.js 的内部逻辑（loadManualLogs 里会处理展开任务的快照刷新）
      loadManualLogs();
    }
    if (activeTab?.dataset.content === 'automation') {
      // 如果有编辑表单存在（无论是展开还是正在折叠），跳过刷新，避免干扰
      const hasEditForm = document.querySelector('.auto-task-edit-wrapper');
      if (!hasEditForm) {
        loadAutoTasks();
      }
    }
  }, 3000);
}

// 页面可见性变化时，暂停或恢复动画相关开关，避免后台标签页导致动画状态错误
document.addEventListener('visibilitychange', () => {
  const list = document.getElementById('manualLogsList');
  if (!list) return;
  if (document.hidden) {
    list.classList.add('no-transitions');
  } else {
    // 恢复前先触发一次轻量刷新，随后移除禁用过渡
    try { import('./logs.js').then(m => m.loadManualLogs && m.loadManualLogs()); } catch {}
    setTimeout(() => list.classList.remove('no-transitions'), 200);
  }
});

function loadFormData() {
  try {
    const savedData = localStorage.getItem('jmcomic_form_data');
    if (!savedData) return; const data = JSON.parse(savedData);
    const setInputValue = (id, v) => { const el = document.getElementById(id); if (el && v) el.value = v; };
    const setSelectValue = (id, v) => { const el = document.getElementById(id); if (el && v) { el.value = v; } };
    if (data.download) {
      setInputValue('downloadDir', data.download.downloadDir);
      setInputValue('dirRule', data.download.dirRule);
      setSelectValue('clientImpl', data.download.clientImpl);
      setSelectValue('imageSuffix', data.download.imageSuffix);
      setInputValue('downloadSpeed', data.download.downloadSpeed);
      setInputValue('dlUsername', data.download.dlUsername);
      setInputValue('dlPassword', data.download.dlPassword);
    }
    if (data.export) {
      setInputValue('expUsername', data.export.expUsername);
      setInputValue('expPassword', data.export.expPassword);
      setSelectValue('zipEnable', data.export.zipEnable);
      setInputValue('zipPassword', data.export.zipPassword);
      setInputValue('saveDir', data.export.saveDir);
      setInputValue('zipFilepath', data.export.zipFilepath);
    }
    if (data.automation) {
      setInputValue('autoDownloadDir', data.automation.autoDownloadDir);
      setSelectValue('autoClientImpl', data.automation.autoClientImpl);
      setSelectValue('autoImageSuffix', data.automation.autoImageSuffix);
      setInputValue('autoDownloadSpeed', data.automation.autoDownloadSpeed);
      setInputValue('autoBatchSize', data.automation.autoBatchSize);
    }
  } catch {}
}

function initAutoSave() {
  ['downloadDir','dirRule','clientImpl','imageSuffix','downloadSpeed','dlUsername','dlPassword','expUsername','expPassword','zipEnable','zipPassword','saveDir','zipFilepath','autoDownloadDir','autoClientImpl','autoImageSuffix','autoDownloadSpeed','autoBatchSize']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.addEventListener('input', saveFormData); el.addEventListener('change', saveFormData); }
    });
}

function saveFormData() {
  const data = {
    download: {
      downloadDir: document.getElementById('downloadDir')?.value || '',
      dirRule: document.getElementById('dirRule')?.value || '',
      clientImpl: document.getElementById('clientImpl')?.value || '',
      imageSuffix: document.getElementById('imageSuffix')?.value || '',
      downloadSpeed: document.getElementById('downloadSpeed')?.value || '',
      dlUsername: document.getElementById('dlUsername')?.value || '',
      dlPassword: document.getElementById('dlPassword')?.value || '',
    },
    export: {
      expUsername: document.getElementById('expUsername')?.value || '',
      expPassword: document.getElementById('expPassword')?.value || '',
      zipEnable: document.getElementById('zipEnable')?.value || '',
      zipPassword: document.getElementById('zipPassword')?.value || '',
      saveDir: document.getElementById('saveDir')?.value || '',
      zipFilepath: document.getElementById('zipFilepath')?.value || '',
    },
    automation: {
      autoDownloadDir: document.getElementById('autoDownloadDir')?.value || '',
      autoClientImpl: document.getElementById('autoClientImpl')?.value || '',
      autoImageSuffix: document.getElementById('autoImageSuffix')?.value || '',
      autoDownloadSpeed: document.getElementById('autoDownloadSpeed')?.value || '',
      autoBatchSize: document.getElementById('autoBatchSize')?.value || '50',
    }
  };
  try { localStorage.setItem('jmcomic_form_data', JSON.stringify(data)); } catch {}
}

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initOperationSwitch();
  initAutomation();
  initDownloadForm();
  initExportForm();
  initLogFilters();
  initCustomSelects();
  initCsvImport();
  document.getElementById('btnResetDownload')?.addEventListener('click', () => {
    document.getElementById('downloadForm')?.reset();
  });
  document.getElementById('btnResetExport')?.addEventListener('click', () => {
    document.getElementById('exportForm')?.reset();
  });
  loadFormData();
  initAutoSave();
  loadManualLogs();
  startAutoRefresh();
});


