function render(value){if(!value)return;document.getElementById('status').textContent=value.text;document.querySelector('progress').hidden=value.error;document.getElementById('retry').hidden=!value.error}
window.gaiaDesktop.onStatus(render);window.gaiaDesktop.status().then(render);
document.getElementById('retry').addEventListener('click',()=>window.gaiaDesktop.retry());
