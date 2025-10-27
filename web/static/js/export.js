import { API_BASE } from './config.js';
import { showMessage } from './utils.js';
import { loadManualLogs } from './logs.js';
export function initExportForm() {
  const form = document.getElementById('exportForm');
  if (!form) return;

  // 密码显隐按钮 - 禁漫密码
  document.getElementById('toggleExpPwd')?.addEventListener('click', () => {
    const pwd = document.getElementById('expPassword');
    if (!pwd) return;
    const isPwd = pwd.getAttribute('type') === 'password';
    pwd.setAttribute('type', isPwd ? 'text' : 'password');
    const icon = document.getElementById('toggleExpPwdIcon');
    if (icon) {
      if (isPwd) {
        // 切换为隐藏图标（眼睛斜杠）
        icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
      } else {
        // 切换为显示图标（眼睛）
        icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
      }
    }
  });

  // 密码显隐按钮 - 压缩密码
  document.getElementById('toggleZipPwd')?.addEventListener('click', () => {
    const pwd = document.getElementById('zipPassword');
    if (!pwd) return;
    const isPwd = pwd.getAttribute('type') === 'password';
    pwd.setAttribute('type', isPwd ? 'text' : 'password');
    const icon = document.getElementById('toggleZipPwdIcon');
    if (icon) {
      if (isPwd) {
        // 切换为隐藏图标（眼睛斜杠）
        icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
      } else {
        // 切换为显示图标（眼睛）
        icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
      }
    }
  });

  // 恢复持久化参数（除本子/章节ID外仅影响导出页控件）
  try {
    const raw = localStorage.getItem('jmcomic_form_data');
    if (raw) {
      const data = JSON.parse(raw);
      const set = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined && val !== null) el.value = val; };
      if (data.export) {
        set('saveDir', data.export.saveDir);
        set('zipEnable', data.export.zipEnable ?? 'false');
        set('zipPassword', data.export.zipPassword);
      }
    }
  } catch {}

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('expUsername').value.trim();
    const password = document.getElementById('expPassword').value;
    if (!username || !password) {
      showMessage('请输入账号和密码', 'error');
      return;
    }

    const config = {
      save_dir: document.getElementById('saveDir').value,
      zip_enable: document.getElementById('zipEnable').value === 'true',
      zip_password: document.getElementById('zipPassword').value,
    };

    // 持久化除本子ID/章节ID外的参数（导出页：保存目录/压缩开关/密码）
    try {
      const raw = localStorage.getItem('jmcomic_form_data');
      const data = raw ? JSON.parse(raw) : {};
      data.export = data.export || {};
      data.export.saveDir = config.save_dir;
      data.export.zipEnable = document.getElementById('zipEnable').value;
      data.export.zipPassword = config.zip_password;
      localStorage.setItem('jmcomic_form_data', JSON.stringify(data));
    } catch {}

    try {
      const response = await fetch(`${API_BASE}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, config })
      });
      const data = await response.json();
      if (response.ok) {
        // 不重置表单，保留账号密码等配置供下次使用
        loadManualLogs();
      } else {
        showMessage(`创建任务失败: ${data.error}`, 'error');
      }
    } catch (error) {
      showMessage(`请求失败: ${error.message}`, 'error');
    }
  });
}


