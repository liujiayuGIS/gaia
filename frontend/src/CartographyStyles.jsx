import React from 'react';

export function FontSelect({value,onChange,options,label='字体'}){
 const fonts=options?.fonts||[],recommended=fonts.filter(f=>f.recommended&&!f.bundled),bundled=fonts.filter(f=>f.bundled),others=fonts.filter(f=>!f.recommended&&!f.bundled);
 return <label className="style-field">{label}<select aria-label={label} value={value||'auto'} onChange={e=>onChange(e.target.value)}>
  <option value="auto">自动中文字体{options?.default_font?' · '+options.default_font:''}</option>
  {recommended.length>0&&<optgroup label="推荐字体">{recommended.map(f=><option key={f.family} value={f.family}>{f.label}</option>)}</optgroup>}
  {bundled.length>0&&<optgroup label="随附开源字体">{bundled.map(f=><option key={f.family} value={f.family}>{f.label}</option>)}</optgroup>}
  {others.length>0&&<optgroup label="本机已安装">{others.map(f=><option key={f.family} value={f.family}>{f.label}</option>)}</optgroup>}
 </select></label>;
}

export function TerrainStyles({layout,save,options}){
 if(layout?.template!=='terrain')return null;
 return <fieldset className="cartographic-styles"><legend>高程与地形</legend>
  <label className="style-field">高程色带<select aria-label="高程色带" value={layout.terrain_palette||'terrain'} onChange={e=>save({terrain_palette:e.target.value})}>{options?.terrain_palettes?.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
  <div className="terrain-swatches" role="group" aria-label="高程色带预览">{options?.terrain_palettes?.map(p=><button key={p.id} aria-label={'色带 '+p.label} aria-pressed={layout.terrain_palette===p.id} title={p.label} onClick={()=>save({terrain_palette:p.id})}><i style={{background:'linear-gradient(90deg,'+p.colors.join(',')+')'}}/><span>{p.label}</span></button>)}</div>
  <label className="check-row"><input type="checkbox" checked={!!layout.terrain_reverse} onChange={e=>save({terrain_reverse:e.target.checked})}/>反转高低值颜色</label>
  <label className="check-row"><input type="checkbox" checked={layout.terrain_hillshade!==false} onChange={e=>save({terrain_hillshade:e.target.checked})}/>叠加山体阴影</label>
  <label className="check-row"><input type="checkbox" checked={layout.terrain_contours!==false} onChange={e=>save({terrain_contours:e.target.checked})}/>显示等高线</label>
  <div className="field-grid"><label className="style-field">等高距 / m<input aria-label="等高距" type="number" min="25" max="2000" value={layout.contour_interval} onChange={e=>{if(e.target.value&&Number(e.target.value)>=25)save({contour_interval:Number(e.target.value)})}}/></label><label className="style-field">图例小数位<select aria-label="图例小数位" value={layout.legend_precision??0} onChange={e=>save({legend_precision:Number(e.target.value)})}>{[0,1,2,3].map(v=><option key={v}>{v}</option>)}</select></label></div>
  <p className="style-help">修改打印地图的高程渲染，同步更新图例；原始 DEM 数值保持不变。</p>
 </fieldset>;
}

export function ElementStyleControls({item,update,options,layout,saveLayout}){
 const set=changes=>update(item.id,changes);
 return <>
  {item.kind==='picture'&&item.north&&<fieldset className="cartographic-styles"><legend>指北针样式</legend><div className="north-presets" role="group" aria-label="指北针样式">{options?.north_styles?.map(s=><button key={s.id} aria-label={'指北针 '+s.label} aria-pressed={(item.north_style||'arrow')===s.id} onClick={()=>set({north_style:s.id})}><img src={'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(s.svg)} alt=""/><span>{s.label}</span></button>)}</div><label className="style-field">指北针颜色<input aria-label="指北针颜色" type="color" value={item.north_color||'#263b43'} onChange={e=>set({north_color:e.target.value})}/></label><p className="style-help">造型与实际导出一致，方向关联主地图真北。</p></fieldset>}
  {item.kind==='scale'&&<fieldset className="cartographic-styles"><legend>比例尺样式</legend><label className="style-field">样式<select aria-label="比例尺样式" value={item.scale_style||'Single Box'} onChange={e=>set({scale_style:e.target.value})}>{options?.scale_styles?.map(s=><option key={s.id} value={s.id}>{s.label}</option>)}</select></label><div className="field-grid"><label className="style-field">显示单位<select aria-label="比例尺单位" value={item.scale_units||'km'} onChange={e=>set({scale_units:e.target.value})}><option value="km">千米</option><option value="m">米</option></select></label><label className="style-field">分段数<select aria-label="比例尺分段数" value={item.scale_segments||2} onChange={e=>set({scale_segments:Number(e.target.value)})}>{[1,2,3,4,5,6,8,10].map(n=><option key={n}>{n}</option>)}</select></label></div><p className="style-help">比例尺关联主地图，切换单位保留实际地面距离。</p></fieldset>}
  {['label','legend','scale'].includes(item.kind)&&<fieldset className="cartographic-styles"><legend>字体与排印</legend><FontSelect options={options} value={item.font_family} onChange={font_family=>set({font_family})} label="元素字体"/><div className="font-specimen" style={{fontFamily:item.font_family==='auto'?undefined:item.font_family}}>地理空间 Aa 0123</div><div className="field-grid"><label className="style-field">字重<select aria-label="元素字重" value={item.font_weight||400} onChange={e=>set({font_weight:Number(e.target.value)})}><option value="400">常规</option><option value="500">中等</option><option value="600">半粗</option><option value="700">粗体</option></select></label>{item.kind!=='label'&&<label className="style-field">字号 / pt<input aria-label="元素字号" type="number" min="1" max="72" value={item.font_size||8} onChange={e=>{if(Number(e.target.value)>0)set({font_size:Number(e.target.value)})}}/></label>}</div>{item.kind==='label'&&<label className="check-row"><input type="checkbox" checked={!!item.italic} onChange={e=>set({italic:e.target.checked})}/>斜体</label>}{item.kind!=='label'&&<label className="style-field">文字颜色<input aria-label="元素颜色" type="color" value={item.color||'#293941'} onChange={e=>set({color:e.target.value})}/></label>}</fieldset>}
  {item.kind==='legend'&&<><label className="style-field">图例列数<select aria-label="图例列数" value={item.legend_columns||1} onChange={e=>set({legend_columns:Number(e.target.value)})}>{[1,2,3,4].map(v=><option key={v}>{v}</option>)}</select></label><TerrainStyles layout={layout} save={saveLayout} options={options}/></>}
 </>;
}
