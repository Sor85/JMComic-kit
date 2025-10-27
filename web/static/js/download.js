import { API_BASE } from './config.js';
import { showMessage, parseIds, parseSpeedLimit } from './utils.js';
import { loadManualLogs } from './logs.js';
export function initDownloadForm() {
  const form = document.getElementById('downloadForm');
  if (!form) return;

  // 压缩配置显示/隐藏
  const enableCompression = document.getElementById('enableCompression');
  const compressionConfig = document.getElementById('compressionConfig');
  if (enableCompression && compressionConfig) {
    enableCompression.addEventListener('change', () => {
      compressionConfig.style.display = enableCompression.checked ? 'block' : 'none';
    });
  }

  // PDF配置显示/隐藏
  const enablePdf = document.getElementById('enablePdf');
  const pdfConfig = document.getElementById('pdfConfig');
  if (enablePdf && pdfConfig) {
    enablePdf.addEventListener('change', () => {
      pdfConfig.style.display = enablePdf.checked ? 'block' : 'none';
    });
  }

  // 密码显隐按钮
  document.getElementById('toggleDlPwd')?.addEventListener('click', () => {
    const pwd = document.getElementById('dlPassword');
    if (!pwd) return;
    const isPwd = pwd.getAttribute('type') === 'password';
    pwd.setAttribute('type', isPwd ? 'text' : 'password');
    const icon = document.getElementById('toggleDlPwdIcon');
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

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const albumIds = parseIds(document.getElementById('albumIds').value);
    const photoIds = parseIds(document.getElementById('photoIds').value);

    if (albumIds.length === 0 && photoIds.length === 0) {
      showMessage('请至少输入一个本子ID或章节ID', 'error');
      return;
    }

    const userDirRule = document.getElementById('dirRule').value.trim();
    const dirRule = 'Bd_' + userDirRule.replace(/\//g, '_');

    const config = {
      download_dir: document.getElementById('downloadDir').value,
      client_impl: document.getElementById('clientImpl').value,
      image_suffix: document.getElementById('imageSuffix').value,
      dir_rule: dirRule,
      username: document.getElementById('dlUsername').value,
      password: document.getElementById('dlPassword').value,
      speed_limit: parseSpeedLimit(document.getElementById('downloadSpeed').value),
    };

    // 添加压缩配置
    const enableCompression = document.getElementById('enableCompression');
    if (enableCompression && enableCompression.checked) {
      const compressionPassword = document.getElementById('compressionPassword').value;
      config.compression = {
        enabled: true,
        format: document.getElementById('compressionFormat').value,
        level: document.getElementById('compressionLevel').value,
        password: compressionPassword || null,
        delete_original: document.getElementById('deleteAfterCompress').checked
      };
    }

    // 添加PDF配置
    const enablePdf = document.getElementById('enablePdf');
    if (enablePdf && enablePdf.checked) {
      const pdfPassword = document.getElementById('pdfPassword').value;
      config.pdf = {
        enabled: true,
        level: document.getElementById('pdfLevel').value,
        password: pdfPassword || null,
        delete_original: document.getElementById('deleteAfterPdf').checked
      };
    }

    try {
      const response = await fetch(`${API_BASE}/api/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ album_ids: albumIds, photo_ids: photoIds, config })
      });
      const data = await response.json();
      if (response.ok) {
        document.getElementById('albumIds').value = '';
        document.getElementById('photoIds').value = '';
        loadManualLogs();
      } else {
        showMessage(`创建任务失败: ${data.error}`, 'error');
      }
    } catch (error) {
      showMessage(`请求失败: ${error.message}`, 'error');
    }
  });
}


