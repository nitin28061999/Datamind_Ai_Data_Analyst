"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
export default function Home(){
 const [sid,setSid]=useState(""),[file,setFile]=useState<File|null>(null),[p,setP]=useState<any>(null),[q,setQ]=useState(""),[out,setOut]=useState<any>(null),[tab,setTab]=useState("Dashboard"),[busy,setBusy]=useState(false);
 useEffect(()=>{fetch(API+"/api/session",{method:"POST"}).then(r=>r.json()).then(x=>setSid(x.session_id))},[]);
 async function upload(){if(!file)return;setBusy(true);const f=new FormData();f.append("file",file);f.append("session_id",sid);const r=await fetch(API+"/api/upload",{method:"POST",body:f});const x=await r.json();setP(x);setBusy(false)}
 async function analyze(){setBusy(true);const r=await fetch(API+"/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sid,question:q})});const x=await r.json();setOut(x);setBusy(false)}
 const nav=["Dashboard","AI Analyst","Python Query","SQL Query","Data Explorer"];
 return <main><header><div><b>DataMind <span>AI</span></b><small>Multimode AI Data Analyst</small></div><em>● Backend Connected</em></header><div className="layout"><aside><h4>WORKSPACE</h4>{nav.map(n=><button className={tab===n?"active":""} onClick={()=>setTab(n)} key={n}>{n}</button>)}<hr/><h4>DATASET</h4><input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setFile(e.target.files?.[0]||null)}/><button className="primary" onClick={upload} disabled={!file||busy}>{busy?"Working...":"Upload Dataset"}</button>{p&&<small>{p.filename}</small>}</aside><section>
 {!p?<div className="welcome"><div>✦</div><h1>Turn data into decisions.</h1><p>Upload a CSV or Excel file for AI dashboards, Python/Pandas analysis, SQL analytics and business insights.</p></div>:
 <><h1>{tab}</h1><p className="muted">{p.rows.toLocaleString()} rows · {p.columns} columns · {p.missing_cells} missing cells</p>
 {tab==="Dashboard"&&<><div className="cards"><Card a="Rows" b={p.rows}/><Card a="Columns" b={p.columns}/><Card a="Missing" b={p.missing_cells}/><Card a="Numeric Fields" b={p.numeric_columns.length}/></div><Panel q={q} setQ={setQ} analyze={analyze} busy={busy}/></>}
 {tab==="AI Analyst"&&<><Panel q={q} setQ={setQ} analyze={analyze} busy={busy}/>{out&&<Result x={out}/>}</>}
 {tab==="Python Query"&&<Runner sid={sid} type="python"/>}
 {tab==="SQL Query"&&<Runner sid={sid} type="sql"/>}
 {tab==="Data Explorer"&&<div className="panel"><h3>Schema</h3><table><tbody>{p.columns_detail.map((c:any)=><tr key={c.name}><td>{c.name}</td><td>{c.dtype}</td><td>{c.missing}</td><td>{c.unique}</td></tr>)}</tbody></table></div>}</>}
 </section></div></main>
}
function Card({a,b}:{a:string,b:any}){return <div className="card"><small>{a}</small><strong>{b.toLocaleString()}</strong></div>}
function Panel({q,setQ,analyze,busy}:{q:string,setQ:any,analyze:any,busy:boolean}){return <div className="panel"><h3>Ask your data</h3><div className="row"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="e.g. Show the top 5 categories by revenue"/><button className="primary" onClick={analyze}>{busy?"Analyzing...":"Analyze"}</button></div><div className="chips">{["Summarize the dataset","Top 5 categories by revenue","Find data quality issues","Show important trends"].map(x=><button key={x} onClick={()=>setQ(x)}>{x}</button>)}</div></div>}
function Result({x}:{x:any}){return <div className="panel"><b>{x.mode?.toUpperCase()}</b><h3>AI Insight</h3><p>{x.answer}</p>{x.result&&<pre>{JSON.stringify(x.result,null,2)}</pre>}{x.sql&&<><h3>SQL</h3><pre>{x.sql}</pre></>}{x.code&&<><h3>Python</h3><pre>{x.code}</pre></>}</div>}
function Runner({sid,type}:{sid:string,type:string}){const [code,setCode]=useState(type==="python"?'result = df.head(10)':'SELECT * FROM dataset LIMIT 20'),[o,setO]=useState<any>();async function run(){const r=await fetch(API+"/api/"+type,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(type==="python"?{session_id:sid,code}:{session_id:sid,sql:code})});setO(await r.json())}return <div className="panel"><h3>{type==="python"?"Pandas / Python":"DuckDB SQL"}</h3><textarea value={code} onChange={e=>setCode(e.target.value)}/><button className="primary" onClick={run}>Run</button>{o&&<pre>{JSON.stringify(o,null,2)}</pre>}</div>}
