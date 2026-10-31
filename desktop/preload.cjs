const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('gaiaDesktop',{
 status:()=>ipcRenderer.invoke('boot-state'),
 retry:()=>ipcRenderer.invoke('boot-retry'),
 onStatus:callback=>{const handler=(_,value)=>callback(value);ipcRenderer.on('boot-status',handler);return()=>ipcRenderer.removeListener('boot-status',handler)}
});
