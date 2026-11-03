export async function copyText(text){
 if(window.gaiaDesktop?.writeClipboard){await window.gaiaDesktop.writeClipboard(text);return}
 try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);return}}catch{}
 const previous=document.activeElement,selection=window.getSelection(),ranges=selection?[...Array(selection.rangeCount)].map((_,i)=>selection.getRangeAt(i).cloneRange()):[];
 const input=document.createElement('textarea');input.value=text;input.setAttribute('aria-label','复制内容');input.style.cssText='position:fixed;left:-10000px;top:0';document.body.appendChild(input);
 try{input.focus();input.select();if(!document.execCommand('copy'))throw new Error('复制失败，请选择文字后使用系统复制。')}
 finally{input.remove();previous?.focus?.({preventScroll:true});if(selection){selection.removeAllRanges();for(const range of ranges)selection.addRange(range)}}
}

export function saveText(text,name){
 const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'})),link=document.createElement('a');
 link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export function messageText(element,fallback=''){
 if(!element)return fallback;
 function walk(node){
  if(node.nodeType===Node.TEXT_NODE)return node.textContent;
  if(node.nodeType!==Node.ELEMENT_NODE||node.hasAttribute('data-copy-ignore'))return '';
  const tag=node.tagName;if(tag==='BR')return '\n';if(tag==='PRE')return node.textContent+'\n\n';
  if(tag==='TR')return [...node.children].map(n=>walk(n)).join('\t')+'\n';
  const text=[...node.childNodes].map(walk).join('');
  if(tag==='LI'){const number=[...node.parentElement.children].indexOf(node)+1;return (node.parentElement.tagName==='OL'?number+'. ':'• ')+text+'\n'}
  return text+(/^(P|H[1-6]|BLOCKQUOTE|UL|OL|TABLE)$/.test(tag)?'\n\n':'');
 }
 return walk(element).replace(/\n{3,}/g,'\n\n').trim()||fallback;
}
