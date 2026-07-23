() => {
  return new Promise(resolve => {
    const sels = document.querySelectorAll('.ant-select-selector');
    sels.forEach(s => {
      const item = s.closest('.ant-form-item');
      if (item && item.textContent.includes('采集结果类型')) {
        s.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
        s.dispatchEvent(new MouseEvent('click', {bubbles:true}));
      }
    });
    setTimeout(() => {
      const opts = document.querySelectorAll('.ant-select-item-option');
      const list = [];
      opts.forEach(o => {
        list.push(o.textContent);
        if (o.textContent.includes('文本')) o.click();
      });
      setTimeout(() => {
        const sels2 = document.querySelectorAll('.ant-select-selector');
        sels2.forEach(s => {
          const item = s.closest('.ant-form-item');
          if (item && item.textContent.includes('异常风险等级')) {
            s.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
            s.dispatchEvent(new MouseEvent('click', {bubbles:true}));
          }
        });
        setTimeout(() => {
          document.querySelectorAll('.ant-select-item-option').forEach(o => {
            if (o.textContent.includes('高风险')) o.click();
          });
          setTimeout(() => {
            document.querySelectorAll('button').forEach(b => {
              if (b.textContent.includes('保存配置')) b.click();
            });
            resolve({types:list, done:true});
          }, 200);
        }, 200);
      }, 300);
    }, 300);
  });
}
