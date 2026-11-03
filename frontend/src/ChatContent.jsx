import React,{useEffect,useRef,useState} from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Copy,Check} from 'lucide-react';
import {copyText} from './chatClipboard';

function CodeBlock({children,onNotice}){
 const [copied,setCopied]=useState(false),timer=useRef();useEffect(()=>()=>clearTimeout(timer.current),[]);
 const element=React.Children.toArray(children).find(React.isValidElement),text=String(element?.props.children??'').replace(/\n$/,''),language=element?.props.className?.replace('language-','')||'代码';
 async function copy(){try{await copyText(text);setCopied(true);clearTimeout(timer.current);timer.current=setTimeout(()=>setCopied(false),1800)}catch(e){onNotice?.(e.message)}}
 return <div className="message-code"><header data-copy-ignore><span>{language}</span><button type="button" onClick={copy} aria-label={copied?'代码已复制':'复制代码'} title="复制代码">{copied?<Check size={13}/>:<Copy size={13}/>}<span>{copied?'已复制':'复制代码'}</span></button></header><pre>{children}</pre></div>;
}

export default function ChatContent({text,onNotice}){
 return <Markdown remarkPlugins={[remarkGfm]} skipHtml components={{
  pre:props=><CodeBlock onNotice={onNotice}>{props.children}</CodeBlock>,
  table:props=><div className="message-table" tabIndex={0} aria-label="回答中的表格"><table>{props.children}</table></div>,
  a:({href,children})=>href?<a href={href} target={href.startsWith('#')?undefined:'_blank'} rel="noopener noreferrer">{children}</a>:<span>{children}</span>,
  img:({src,alt})=>src?<a href={src} target="_blank" rel="noopener noreferrer">{alt||'查看图片'}</a>:<span>{alt||'图片地址无效'}</span>
 }}>{text}</Markdown>;
}
