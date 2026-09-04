import {useEffect,useMemo,useState} from 'react'
import {Activity, Boxes, BrainCircuit, CheckCircle2, Cpu, Database, FlaskConical, GitCompareArrows, HardDriveDownload, RefreshCw, ShieldCheck, TriangleAlert} from 'lucide-react'
import {api,UserMe} from './api'

type Model={id:string;code:string;name:string;provider:string;backend:string;version:string;license_name:string;commercial_use:boolean;active:boolean;stage:string;artifact_uri?:string;artifact_sha256?:string;available:boolean;framework?:string;class_map:Record<string,string>;metrics:Record<string,number>;metadata:Record<string,unknown>}
type Dataset={id:string;code:string;name:string;license_name:string;source_url?:string;active:boolean;created_at:string}
type Run={id:string;status:string;base_model:string;epochs:number;image_size:number;device:string;metrics:Record<string,number>;command_line?:string;created_at:string}
type Dep={id:string;model_version_id:string;camera_id?:string;mode:string;enabled:boolean;started_at:string}
type Shadow={samples:number;agreements:number;agreement_ratio:number;by_ppe:Record<string,{samples:number;agreements:number;agreement_ratio:number}>}
type Overview={models:Model[];datasets:Dataset[];training_runs:Run[];deployments:Dep[];shadow:Shadow;policy:{ultralytics_used:boolean;training_stack:string;runtime:string;bootstrap:string}}
type Org={id:string;code:string;name:string}

export default function MLPage({me}:{me:UserMe}){
 const [data,setData]=useState<Overview|null>(null),[orgs,setOrgs]=useState<Org[]>([]),[orgId,setOrgId]=useState(me.organization_id||''),[err,setErr]=useState('')
 async function refresh(){setErr('');try{
   let oid=orgId
   if(!oid&&me.role_codes.includes('SUPERADMIN')){const o=await api<Org[]>('/organizations');setOrgs(o);if(o[0]){oid=o[0].id;setOrgId(oid)}}
   const qs=oid?`?organization_id=${encodeURIComponent(oid)}`:''
   setData(await api<Overview>(`/ml/overview${qs}`))
 }catch(e){setErr((e as Error).message)}}
 useEffect(()=>{refresh()},[orgId])
 const bootstrap=useMemo(()=>data?.models.find(m=>m.code==='INTEL_WORKER_SAFETY_BOOTSTRAP'),[data])
 const hys=useMemo(()=>data?.models.filter(m=>m.backend==='onnx_yolox_ppe')||[],[data])
 return <div className="ml-workspace">
  <section className="ml-command"><div><div className="eyebrow">BLOQUE 9 · v1.0.0 · MODELO DESACOPLADO</div><h3>Dataset HYS, Model Registry y despliegue SHADOW</h3><p>El detector deja de depender del baseline sintético. El entrenamiento HYS usa YOLOX 0.3.0 bajo Apache-2.0 y el runtime productivo usa ONNX Runtime. Ultralytics no forma parte del pipeline.</p></div><div className="ml-license"><ShieldCheck/><div><span>POLÍTICA DE LICENCIAS</span><b>ULTRALYTICS: NO USADO</b><small>YOLOX Apache-2.0 · Bootstrap Intel MIT</small></div></div></section>
  <div className="ml-toolbar">{me.role_codes.includes('SUPERADMIN')&&orgs.length>0&&<select value={orgId} onChange={e=>setOrgId(e.target.value)}>{orgs.map(o=><option key={o.id} value={o.id}>{o.code} — {o.name}</option>)}</select>}<button onClick={refresh}><RefreshCw size={14}/>ACTUALIZAR</button></div>
  {err&&<div className="error">{err}</div>}
  <section className="ml-kpis"><div><Database/><span>DATASETS HYS</span><b>{data?.datasets.length??'—'}</b></div><div><BrainCircuit/><span>MODELOS PPE</span><b>{data?.models.length??'—'}</b></div><div><FlaskConical/><span>TRAINING RUNS</span><b>{data?.training_runs.length??'—'}</b></div><div><GitCompareArrows/><span>SHADOW SAMPLES</span><b>{data?.shadow.samples??'—'}</b></div><div><CheckCircle2/><span>ACUERDO SHADOW</span><b>{data?.shadow.samples?`${(data.shadow.agreement_ratio*100).toFixed(1)}%`:'—'}</b></div></section>
  <section className="ml-grid">
   <div className="ml-panel"><div className="panel-title"><span>MODELOS REGISTRADOS</span><em>{data?.models.length||0}</em></div><div className="ml-models">{data?.models.map(m=><div className={`ml-model ${m.stage?.toLowerCase()}`} key={m.id}><div className="ml-model-head"><BrainCircuit/><div><small>{m.provider} · {m.backend}</small><b>{m.name}</b><span>{m.version}</span></div><i className={m.available?'ok':'wait'}>{m.available?'ARTIFACT READY':'ARTIFACT AUSENTE'}</i></div><div className="ml-tags"><span>{m.license_name}</span><span>{m.stage}</span>{Object.values(m.class_map||{}).map(c=><span key={c}>{c}</span>)}</div><small className="ml-artifact">{m.artifact_uri||'Modelo embebido / sin artifact externo'}</small></div>)}</div></div>
   <div className="ml-panel"><div className="panel-title"><span>BOOTSTRAP VIDEO REAL</span><em>{bootstrap?.available?'READY':'PENDIENTE'}</em></div><div className={`bootstrap-state ${bootstrap?.available?'ready':'pending'}`}><HardDriveDownload/><h4>Intel Worker Safety Gear</h4><p>Detector real y permisivo para <b>HELMET + VEST</b>. Sirve para probar video real inmediatamente y como candidato SHADOW mientras se entrena el modelo HYS propio.</p><div><span>Licencia MIT</span><span>OpenVINO IR</span><span>CPU</span></div><strong>{bootstrap?.available?'MODELO INSTALADO':'Ejecutar scripts\\instalar_bootstrap_intel_bloque9.ps1'}</strong></div><div className="ml-safety-note"><TriangleAlert/><span>SAFETY_SHOES no está soportado por el bootstrap Intel: permanece INCIERTO/NO_VISIBLE y nunca genera incumplimiento por ausencia.</span></div></div>
  </section>
  <section className="ml-grid">
   <div className="ml-panel"><div className="panel-title"><span>DATASET HYS</span><em>PROPIO</em></div>{data?.datasets.length?<table className="ml-table"><thead><tr><th>CÓDIGO</th><th>NOMBRE</th><th>LICENCIA</th></tr></thead><tbody>{data.datasets.map(d=><tr key={d.id}><td>{d.code}</td><td>{d.name}</td><td>{d.license_name}</td></tr>)}</tbody></table>:<div className="ml-empty"><Database/><b>Sin dataset registrado</b><span>Extraé frames, etiquetá PERSON/HELMET/VEST/SAFETY_SHOES y congelá v0001.</span></div>}</div>
   <div className="ml-panel"><div className="panel-title"><span>TRAINING PIPELINE</span><em>YOLOX</em></div><div className="ml-pipeline"><span>FRAMES</span><b>→</b><span>LABELS</span><b>→</b><span>COCO</span><b>→</b><span>YOLOX</span><b>→</b><span>ONNX</span><b>→</b><span>REGISTRY</span><b>→</b><span>SHADOW</span></div><div className="ml-stack"><div><Cpu/><b>{data?.policy.training_stack||'YOLOX 0.3.0 / Apache-2.0'}</b><small>Entrenamiento aislado en perfil Docker `training`.</small></div><div><Boxes/><b>{data?.policy.runtime||'ONNX Runtime CPU'}</b><small>El servidor de producción no necesita YOLOX instalado.</small></div></div></div>
  </section>
  <section className="ml-grid">
   <div className="ml-panel"><div className="panel-title"><span>SHADOW DEPLOYMENT</span><em>{data?.deployments.filter(x=>x.mode==='SHADOW').length||0} ACTIVOS</em></div><div className="shadow-score"><GitCompareArrows/><div><span>ACUERDO GLOBAL</span><b>{data?.shadow.samples?`${(data.shadow.agreement_ratio*100).toFixed(1)}%`:'SIN MUESTRAS'}</b><small>{data?.shadow.samples||0} observaciones</small></div></div><div className="shadow-ppe">{Object.entries(data?.shadow.by_ppe||{}).map(([k,v])=><div key={k}><span>{k}</span><b>{(v.agreement_ratio*100).toFixed(1)}%</b><small>{v.samples} muestras</small></div>)}</div></div>
   <div className="ml-panel"><div className="panel-title"><span>MODELOS HYS ONNX</span><em>{hys.length}</em></div>{hys.length?hys.map(m=><div className="hys-model" key={m.id}><Activity/><div><b>{m.code}</b><span>{m.stage} · {m.version}</span><small>{Object.entries(m.metrics||{}).map(([k,v])=>`${k}=${v}`).join(' · ')||'Métricas pendientes'}</small></div></div>):<div className="ml-empty"><BrainCircuit/><b>Aún sin modelo HYS entrenado</b><span>El bootstrap real permite avanzar hoy; el modelo HYS se promoverá sólo después de test independiente + SHADOW.</span></div>}</div>
  </section>
 </div>
}
