import React,{useEffect,useId,useRef,useState} from 'react';
import {Copy,Check,Reply,PencilLine,RefreshCw,ThumbsUp,ThumbsDown,Volume2,Square,MoreHorizontal,Download,FileText} from 'lucide-react';
import {copyText,saveText,messageText} from './chatClipboard';

function Action({label,children,...props}){return <button type="button" aria-label={label} title={label} {...props}>{children}</button>}

function useSpeech(id,onNotice){
 const [voices,setVoices]=useState([]),[speaking,setSpeaking]=useState(false),owned=useRef(false),generation=useRef(0),queue=useRef([]);
 useEffect(()=>{
  const synth=window.speechSynthesis;if(!synth)return;
  const update=()=>setVoices(synth.getVoices().filter(v=>v.localService)),other=e=>{if(e.detail!==id){owned.current=false;generation.current++;setSpeaking(false)}};
  update();synth.addEventListener('voiceschanged',update);window.addEventListener('gaia-speech-owner',other);
  return()=>{synth.removeEventListener('voiceschanged',update);window.removeEventListener('gaia-speech-owner',other);generation.current++;if(owned.current)synth.cancel()};
 },[id]);
 function toggle(text){
  const synth=window.speechSynthesis;if(!synth||!voices.length)return;
  if(owned.current){generation.current++;owned.current=false;synth.cancel();setSpeaking(false);return}
  const token=++generation.current;window.dispatchEvent(new CustomEvent('gaia-speech-owner',{detail:id}));synth.cancel();owned.current=true;setSpeaking(true);
  const voice=voices.find(v=>/^zh/i.test(v.lang))||voices.find(v=>v.default)||voices[0];
  const chars=Array.from(text),chunks=[];for(let i=0;i<chars.length;i+=220)chunks.push(chars.slice(i,i+220).join(''));
  queue.current=chunks.map((chunk,i)=>{const u=new SpeechSynthesisUtterance(chunk);u.voice=voice;u.lang=voice.lang;
   u.onend=()=>{if(i===chunks.length-1&&generation.current===token){owned.current=false;setSpeaking(false)}};
   u.onerror=e=>{if(generation.current!==token)return;owned.current=false;setSpeaking(false);if(!['canceled','interrupted'].includes(e.error))onNotice?.('系统语音暂不可用，请检查本地语音设置。')};return u});
  for(const u of queue.current)synth.speak(u);
 }
 return {speaking,available:voices.length>0,toggle};
}

export default function MessageActions({run,role,bodyRef,onReply,onEdit,onReanswer,onFeedback,feedback,busy,onNotice}){
 const user=role==='user',text=user?run.message_input:run.message||'',[copied,setCopied]=useState(false),[rating,setRating]=useState(false),[open,setOpen]=useState(false),timer=useRef(),menu=useRef(),opener=useRef(),menuId=useId();
 const speech=useSpeech(run.id+':'+role,onNotice),time=run[user?'created_at':'finished_at']||(!user?run.created_at:null),date=time?new Date(time):null,valid=date&&!Number.isNaN(date.getTime());
 const plain=()=>messageText(bodyRef.current,text);
 useEffect(()=>{const close=()=>{if(menu.current?.matches(':popover-open'))menu.current.hidePopover()};const history=bodyRef.current?.closest('.assistant-history');window.addEventListener('resize',close);history?.addEventListener('scroll',close);return()=>{clearTimeout(timer.current);window.removeEventListener('resize',close);history?.removeEventListener('scroll',close)}},[]);
 function positionMenu(event){const shown=event.newState==='open';setOpen(shown);if(!shown)return;const r=opener.current.getBoundingClientRect(),box=menu.current.getBoundingClientRect();menu.current.style.left=Math.max(12,Math.min(innerWidth-box.width-12,r.right-box.width))+'px';menu.current.style.top=(r.top>box.height+12?r.top-box.height-5:Math.min(innerHeight-box.height-12,r.bottom+5))+'px'}
 async function copy(markdown=false){try{await copyText(markdown||user?text:plain());setCopied(true);clearTimeout(timer.current);timer.current=setTimeout(()=>setCopied(false),1800)}catch(e){onNotice?.(e.message)}}
 function more(fn){menu.current?.hidePopover();fn()}
 async function rate(value){setRating(true);try{await onFeedback(feedback===value?null:value)}finally{setRating(false)}}
 return <div className={'message-actions '+(user?'user-message-actions':'answer-message-actions')} role="group" aria-label={user?'提问操作':'回答操作'}>
  {user&&valid&&<time dateTime={date.toISOString()} title={date.toLocaleString()}>{date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</time>}
  <Action label={copied?'已复制':user?'复制提问':'复制回答'} disabled={!text} onClick={()=>copy()}>{copied?<Check size={15}/>:<Copy size={15}/>}</Action>
  <Action label={user?'引用提问':'引用回复'} disabled={busy||!text||!onReply} onClick={()=>onReply?.(run,role,plain())}><Reply size={15}/></Action>
  {user?<Action label="编辑为新提问" disabled={busy||!onEdit} onClick={()=>onEdit?.(run)}><PencilLine size={15}/></Action>:<>
   <Action label="赞同回答" disabled={!text||rating||!onFeedback} aria-pressed={feedback==='up'} onClick={()=>rate('up')}><ThumbsUp size={15}/></Action>
   <Action label="不满意" disabled={!text||rating||!onFeedback} aria-pressed={feedback==='down'} onClick={()=>rate('down')}><ThumbsDown size={15}/></Action>
   <Action label="重新回答" title="根据原结果重新组织说明，不重复执行 GIS；离线模式重述原记录" disabled={busy||!text||!onReanswer||['queued','running','waiting_approval'].includes(run.status)} onClick={()=>onReanswer?.(run)}><RefreshCw size={15}/></Action>
   <Action label={speech.speaking?'停止朗读':speech.available?'朗读回答':'朗读不可用：未找到系统离线语音'} disabled={!text||!speech.available} aria-pressed={speech.speaking} onClick={()=>speech.toggle(plain())}>{speech.speaking?<Square size={15}/>:<Volume2 size={15}/>}</Action>
   <button ref={opener} type="button" popoverTarget={menuId} aria-label="更多回答操作" title="更多回答操作" aria-expanded={open}><MoreHorizontal size={17}/></button><div id={menuId} popover="auto" className="message-more-items" ref={menu} onToggle={positionMenu}>
    <button type="button" disabled={!text} onClick={()=>more(()=>copy(true))}><Copy size={14}/>复制 Markdown</button>
    <button type="button" disabled={!text} onClick={()=>more(()=>saveText(text,'GAIA-回答-'+run.id.slice(0,8)+'.md'))}><Download size={14}/>保存回答为 Markdown</button>
    <button type="button" onClick={()=>more(()=>saveText('# GAIA 对话\n\n## 提问\n\n'+run.message_input+'\n\n## 回答\n\n'+text+'\n','GAIA-对话-'+run.id.slice(0,8)+'.md'))}><FileText size={14}/>导出本轮对话</button>
   </div>
   {valid&&<time dateTime={date.toISOString()} title={date.toLocaleString()}>{date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</time>}
  </>}
  <span className="visually-hidden" role="status">{copied?'已复制到剪贴板':''}</span>
 </div>;
}
