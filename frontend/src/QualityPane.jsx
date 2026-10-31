import React,{useEffect,useState} from 'react';
import {ShieldCheck,AlertTriangle,Check,LoaderCircle,Download} from 'lucide-react';
import {api,post,patch} from './shared';

const checkNames={page_bounds:'版面边界',text_size:'文字字号',text_fit:'文本框容纳',map_link:'地图要素关联',legend_coverage:'图例覆盖',scale_value:'比例尺单位与长度',layout_overlap:'布局元素遮挡',label_collisions:'地图标注碰撞',unplaced_labels:'标注放置',preview_dimensions:'预览尺寸',preview_content:'预览内容',input_version:'输入数据版本',strict_coverage:'完整核验覆盖',overlay_coverage:'叠加范围与面积',count_rows:'计数区域数量',count_regions:'计数区域保留',count_field:'输出计数字段',independent_point_count:'点计数复算',buffer_distance:'缓冲距离复算',output_grid:'输出网格对齐',raster_finite:'有效像元数值',nodata_propagation:'缺失像元传播',route_connectivity_cost:'路线连通与成本',network_positive_cost:'路网正成本',distance_crs:'距离坐标系',distance_unit:'距离单位',count_geometry:'点面几何类型',count_overlap:'区域重叠口径',count_boundary:'边界计数口径',population_semantics:'人口数量含义',population_unit:'人口单位',population_integral:'人口密度积分',required_fields:'必要字段',data_dates:'数据日期',date_gap:'日期差',travel_mode:'交通方式',network_cost:'路网成本单位',network_crs:'路网坐标系',network_speed:'路网速度',walking_speed:'步行速度',raster_alignment:'输入栅格对齐',terrain_horizontal:'地形水平单位',elevation_unit:'高程单位',categorical_resampling:'分类重采样',validator_execution:'核验器执行'};
export function QualityDetails({report}){
 if(!report)return null;
 const reports=[report,...(report.quality_reports||[]).flatMap(q=>[q.preflight,q.domain]),...(report.map_reviews||[])];
 const checks=reports.flatMap(r=>r?.checks||[]),errors=[...new Set(reports.flatMap(r=>r?.errors||[]))],warnings=[...new Set(reports.flatMap(r=>r?.warnings||[]))],unknown=[...new Set(reports.flatMap(r=>r?.unverified||[]))];
 const groups=Object.entries(Object.groupBy(checks,c=>c.code));
 return <details className="quality-details"><summary><ShieldCheck size={14}/>检查依据与覆盖范围{checks.length>0&&<span>{checks.length} 项</span>}</summary>
 {errors.map((x,i)=><p className="quality-error" key={'e'+i}><AlertTriangle size={13}/>{x}</p>)}
 {warnings.map((x,i)=><p key={'w'+i}><AlertTriangle size={13}/>{x}</p>)}
 {checks.length>0&&<ul>{groups.map(([code,items])=>{const passed=items.filter(c=>c.status==='pass').length;return <li key={code}>{passed===items.length?<Check size={12}/>:<AlertTriangle size={12}/>}<span>{checkNames[code]||'专项条件检查'}<small>{passed} / {items.length} 项通过</small></span></li>})}</ul>}
 {unknown.length>0&&<div className="quality-unverified"><strong>尚未验证</strong>{unknown.map((x,i)=><p key={i}>{x}</p>)}</div>}
 {report.report_url&&<a href={report.report_url} download><Download size={13}/>下载核验记录</a>}
 </details>;
}

export function LayerSemantics({layer,onSaved,notice}){
 const initial=()=>({quantity:layer.semantics?.quantity||'unspecified',unit:layer.semantics?.unit||'',reference_date:layer.semantics?.reference_date||'',source:layer.semantics?.source||'',evidence:layer.semantics?.evidence||'',basis:layer.semantics?.basis||'user_declared'});
 const [value,setValue]=useState(initial),[saving,setSaving]=useState(false);
 useEffect(()=>setValue(initial()),[layer.id,layer.semantics]);
 const change=(k,v)=>setValue(x=>({...x,[k]:v}));
 async function save(e){e.preventDefault();setSaving(true);try{await patch('/layers/'+layer.id+'/semantics',{...value,reference_date:value.reference_date||null});await onSaved();notice('空间语义已保存，并绑定当前数据版本。')}catch(e){notice(e.message)}finally{setSaving(false)}}
 return <details className="semantic-editor"><summary>数据含义与时间</summary><p>以数据文档或已确认的信息为依据；未知项留空。</p><form onSubmit={save}>
 <label className="field-label">数量含义<select aria-label="数量含义" value={value.quantity} onChange={e=>change('quantity',e.target.value)}>{[['unspecified','尚未声明'],['count_per_cell','每像元人数'],['density','人口密度'],['elevation','高程'],['categorical','类别编码'],['other','其他数值']].map(([id,t])=><option key={id} value={id}>{t}</option>)}</select></label>
 <label className="field-label">数据单位<input aria-label="数据单位" value={value.unit} placeholder="m / people / people/km2" onChange={e=>change('unit',e.target.value)}/></label>
 <label className="field-label">数据日期<input aria-label="数据日期" type="date" value={value.reference_date} onChange={e=>change('reference_date',e.target.value)}/></label>
 <label className="field-label">来源<input aria-label="语义来源" required maxLength={1000} value={value.source} onChange={e=>change('source',e.target.value)} placeholder="数据说明文档或来源机构"/></label>
 <label className="field-label">确认依据<textarea aria-label="语义确认依据" required maxLength={2000} value={value.evidence} onChange={e=>change('evidence',e.target.value)} placeholder="例如：数据说明写明像元值是每平方公里人数"/></label>
 <button disabled={saving} type="submit">{saving?'保存中…':'保存数据说明'}</button></form></details>;
}

export function SpatialOptions({value,onChange,algorithmId}){
 const network=/shortestpath|servicearea/.test(algorithmId||'');
 const change=(k,v)=>onChange({...value,[k]:v});
 return <details className="spatial-options"><summary>分析口径与验收</summary>
 <label>分析对象<select aria-label="分析对象" value={value.quantity||'general'} onChange={e=>change('quantity',e.target.value)}><option value="general">一般空间分析</option><option value="population">人口数量分析</option></select></label>
 <label>距离参数单位<select aria-label="距离参数单位" value={value.distance_unit||''} onChange={e=>change('distance_unit',e.target.value||null)}><option value="">按算法契约检查</option><option value="m">米</option><option value="km">千米</option><option value="layer_units">明确采用图层坐标单位</option></select></label>
 {network&&<><label>交通方式<select aria-label="交通方式" value={value.travel_mode||''} onChange={e=>change('travel_mode',e.target.value||null)}><option value="">请选择</option><option value="walk">步行</option><option value="cycle">骑行</option><option value="drive">驾车</option></select></label><label>成本单位<select aria-label="成本单位" value={value.cost_unit||''} onChange={e=>change('cost_unit',e.target.value||null)}><option value="">请选择</option><option value="h">小时（15 分钟 = 0.25）</option><option value="m">米</option></select></label></>}
 <label>区域边界<select aria-label="区域边界" value={value.boundary||'covers'} onChange={e=>change('boundary',e.target.value)}><option value="covers">包含边界</option><option value="contains">不包含边界</option></select></label>
 <label>重叠区域<select aria-label="重叠区域" value={value.overlap||'per_region'} onChange={e=>change('overlap',e.target.value)}><option value="per_region">各区域分别计数</option><option value="unique">需要全局去重</option></select></label>
 <label>验收要求<select aria-label="验收要求" value={value.verification||'standard'} onChange={e=>change('verification',e.target.value)}><option value="standard">标准：列出检查与未覆盖项</option><option value="strict">严格：不接受缺失或抽样核验</option></select></label>
 </details>;
}

export default function QualityPane({revision,refresh,notice,onAssistant}){
 const [audit,setAudit]=useState(null),[busy,setBusy]=useState(''),[error,setError]=useState('');
 useEffect(()=>{setAudit(null)},[revision]);
 async function inspect(){setBusy('正在生成地图并检查');setError('');try{setAudit(await post('/layout/audit',{}))}catch(e){setError(e.message)}finally{setBusy('')}}
 async function polish(){setBusy('正在调整版式');setError('');try{await post('/layout/polish',{preset:'publication'});await refresh();notice('已调整说明字号与图例位置，请重新检查地图。')}catch(e){setError(e.message)}finally{setBusy('')}}
 return <section className="task-pane quality-pane"><header className="pane-title"><h2>质量与审图</h2><ShieldCheck size={16}/></header><div className="pane-fields"><p>检查出图布局、图例和标注；结合真实地图预览复核成果。</p><div className="button-row"><button disabled={!!busy} onClick={inspect}>{busy?<LoaderCircle className="spin" size={14}/>:<ShieldCheck size={14}/>}检查当前布局</button><button disabled={!!busy} onClick={polish}>应用出版版式</button></div>{busy&&<p role="status">{busy}…</p>}{error&&<p className="form-error" role="alert">{error}</p>}
 {audit&&<><a href={audit.preview_url} target="_blank" rel="noreferrer"><img className="audit-preview" src={audit.preview_url} alt="本次审阅的完整地图布局"/></a><p>{audit.quality.cartography.passed?'已覆盖的程序检查通过':'程序检查发现问题'} · 视觉审阅尚需完成</p><QualityDetails report={audit.quality.cartography}/><button onClick={()=>onAssistant('请审阅当前地图：调用 inspect_map 查看真实地图，检查标注、图例、比例尺、指北针、留白和配色。给出具体问题，修正后重新出图并记录视觉审阅。')}>交给 GAIA 视觉审阅</button><small>需连接支持图像输入的模型；地图预览会发送给模型。</small></>}
 </div></section>;
}
