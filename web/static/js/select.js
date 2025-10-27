function createTrigger(selectedText) {
  const trigger = document.createElement('div');
  trigger.className = 'custom-select-trigger';
  trigger.innerHTML = `
    <span class="custom-select-text">${selectedText}</span>
    <span class="custom-select-arrow">
      <svg viewBox="0 0 12 12">
        <path d="M6 9L1.5 4.5h9L6 9z"/>
      </svg>
    </span>
  `;
  return trigger;
}

function createOption(option, index, selectElement, trigger, dropdown, wrapper) {
  const optionEl = document.createElement('div');
  optionEl.className = 'custom-select-option';
  if (index === selectElement.selectedIndex) optionEl.classList.add('selected');
  optionEl.textContent = option.text;
  optionEl.dataset.value = option.value;
  optionEl.dataset.index = index;
  optionEl.addEventListener('click', (e) => {
    e.stopPropagation();
    selectElement.selectedIndex = index;
    selectElement.dispatchEvent(new Event('change', { bubbles: true }));
    trigger.querySelector('.custom-select-text').textContent = option.text;
    dropdown.querySelectorAll('.custom-select-option').forEach(opt => opt.classList.remove('selected'));
    optionEl.classList.add('selected');
    wrapper.classList.remove('active');
  });
  return optionEl;
}

export function createCustomSelect(selectElement) {
  // 如果已经被包装，跳过
  if (selectElement.parentElement?.classList.contains('custom-select-wrapper')) return;
  
  // 如果select不可见或被禁用，跳过
  if (!selectElement || selectElement.style.display === 'none') return;
  
  const wrapper = document.createElement('div');
  wrapper.className = 'custom-select-wrapper';
  
  // 复制原select的内联样式到wrapper（如flex属性）
  if (selectElement.style.cssText) {
    const styleProps = ['flex', 'flex-grow', 'flex-shrink', 'flex-basis', 'width', 'min-width', 'max-width'];
    styleProps.forEach(prop => {
      const value = selectElement.style[prop];
      if (value) {
        wrapper.style[prop] = value;
      }
    });
  }
  
  const selectedOption = selectElement.options[selectElement.selectedIndex];
  const selectedText = selectedOption ? selectedOption.text : '';
  const trigger = createTrigger(selectedText);
  const dropdown = document.createElement('div');
  dropdown.className = 'custom-select-dropdown';
  Array.from(selectElement.options).forEach((option, index) => {
    const optionEl = createOption(option, index, selectElement, trigger, dropdown, wrapper);
    dropdown.appendChild(optionEl);
  });
  
  // 确保正确插入DOM
  const parent = selectElement.parentNode;
  if (!parent) {
    console.warn('Select element has no parent, skipping custom select creation');
    return;
  }
  
  parent.insertBefore(wrapper, selectElement);
  wrapper.appendChild(selectElement);
  wrapper.appendChild(trigger);
  wrapper.appendChild(dropdown);
  
  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    document.querySelectorAll('.custom-select-wrapper.active').forEach(w => { if (w !== wrapper) w.classList.remove('active'); });
    wrapper.classList.toggle('active');
  });
  dropdown.addEventListener('click', (e) => { e.stopPropagation(); });
}

export function initCustomSelects() {
  console.log('[Custom Select] 开始初始化自定义下拉组件...');
  
  // 初始化 .input-group 中的所有 select
  const inputGroupSelects = document.querySelectorAll('.input-group select');
  console.log(`[Custom Select] 找到 ${inputGroupSelects.length} 个 .input-group 中的 select 元素`);
  
  inputGroupSelects.forEach((select, index) => {
    console.log(`[Custom Select] 正在初始化第 ${index + 1} 个 select: ${select.id || '(无ID)'}`);
    createCustomSelect(select);
  });
  
  // 特殊处理 csvFileSelect（不在 .input-group 中）
  const csvFileSelect = document.getElementById('csvFileSelect');
  if (csvFileSelect) {
    console.log('[Custom Select] 正在初始化 csvFileSelect');
    createCustomSelect(csvFileSelect);
  }
  
  // 验证结果
  const wrapperCount = document.querySelectorAll('.custom-select-wrapper').length;
  console.log(`[Custom Select] 初始化完成，共创建 ${wrapperCount} 个自定义下拉组件`);
  
  // 检查是否有select没有被包装
  const unwrappedSelects = Array.from(document.querySelectorAll('select')).filter(
    select => !select.parentElement?.classList.contains('custom-select-wrapper')
  );
  if (unwrappedSelects.length > 0) {
    console.warn(`[Custom Select] 警告：还有 ${unwrappedSelects.length} 个 select 元素没有被自定义化:`, 
      unwrappedSelects.map(s => s.id || s.name || '(无标识)'));
  }
}

export function updateCustomSelectText(selectElement) {
  const wrapper = selectElement.closest('.custom-select-wrapper');
  if (!wrapper) return;
  const trigger = wrapper.querySelector('.custom-select-trigger .custom-select-text');
  const dropdown = wrapper.querySelector('.custom-select-dropdown');
  if (trigger) {
    const selectedOption = selectElement.options[selectElement.selectedIndex];
    trigger.textContent = selectedOption ? selectedOption.text : '';
  }
  if (dropdown) {
    dropdown.querySelectorAll('.custom-select-option').forEach((opt, index) => {
      if (index === selectElement.selectedIndex) opt.classList.add('selected');
      else opt.classList.remove('selected');
    });
  }
}

export function refreshCustomSelect(selectElement) {
  const wrapper = selectElement.closest('.custom-select-wrapper');
  if (!wrapper) return;
  
  const trigger = wrapper.querySelector('.custom-select-trigger');
  const dropdown = wrapper.querySelector('.custom-select-dropdown');
  
  if (!dropdown || !trigger) return;
  
  // 清空现有选项
  dropdown.innerHTML = '';
  
  // 重新创建所有选项
  Array.from(selectElement.options).forEach((option, index) => {
    const optionEl = createOption(option, index, selectElement, trigger, dropdown, wrapper);
    dropdown.appendChild(optionEl);
  });
  
  // 更新触发器文本
  const selectedOption = selectElement.options[selectElement.selectedIndex];
  trigger.querySelector('.custom-select-text').textContent = selectedOption ? selectedOption.text : '';
}

// close on outside click
window.addEventListener('click', () => {
  document.querySelectorAll('.custom-select-wrapper.active').forEach(wrapper => wrapper.classList.remove('active'));
});
