import { useState, useEffect, useRef } from 'react'

const STEPS = [
  { key: 'planner', label: 'Understanding request' },
  { key: 'researcher', label: 'Researching requirements + RAG' },
  { key: 'developer', label: 'Generating implementation' },
  { key: 'tester', label: 'Running tests' },
  { key: 'reviewer', label: 'Security review' },
  { key: 'human_approval', label: 'Human approval' },
]

function Stepper({ current, logs, done }) {
  const stepIndex = (s) => {
    const order = ['planner','researcher','developer','tester','reviewer','human_approval']
    return order.indexOf(s)
  }
  const curIdx = stepIndex(current)

  return (
    <div className="space-y-3">
      {STEPS.map((s, i) => {
        // Deduplicate researcher label handling
        const isActive = s.key === current && !done
        const isDone = stepIndex(s.key) < curIdx || (done && i < STEPS.length)
        const isFailed = false
        return (
          <div key={i} className="flex items-center gap-3">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium border
              ${isDone ? 'bg-emerald-500 border-emerald-500 text-white' : ''}
              ${isActive ? 'bg-cyan-500 border-cyan-500 text-white animate-pulse' : ''}
              ${!isActive && !isDone ? 'bg-white border-slate-200 text-slate-400' : ''}`}>
              {isDone ? '✓' : isActive ? '●' : '○'}
            </div>
            <span className={`text-sm ${isActive ? 'text-slate-900 font-medium' : isDone ? 'text-slate-600' : 'text-slate-400'}`}>
              {s.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function App() {
  const [request, setRequest] = useState('Build a REST API for employee management with FastAPI, SQLite, JWT authentication, CRUD operations, pytest and clean layered architecture.')
  const [taskId, setTaskId] = useState(null)
  const [status, setStatus] = useState('idle')
  const [currentStep, setCurrentStep] = useState('planner')
  const [logs, setLogs] = useState([])
  const [artifacts, setArtifacts] = useState([])
  const [review, setReview] = useState(null)
  const [health, setHealth] = useState(null)
  const [streamDone, setStreamDone] = useState(false)
  const [activeTab, setActiveTab] = useState('workflow')
  const [bench, setBench] = useState(null)
  const [ragStats, setRagStats] = useState(null)
  const eventRef = useRef(null)

  useEffect(() => {
    fetch('/health').then(r=>r.json()).then(setHealth).catch(()=>setHealth({status:'offline'}))
    fetch('/api/evaluation/results').then(r=>r.json()).then(setBench).catch(()=>{})
    fetch('/api/rag/stats').then(r=>r.json()).then(setRagStats).catch(()=>{})
  }, [])

  const startTask = async () => {
    if(!request.trim()) return
    setLogs([])
    setArtifacts([])
    setReview(null)
    setStreamDone(false)
    setStatus('running')
    setCurrentStep('planner')
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ request, max_retries: 2 })
    })
    const data = await res.json()
    if(data.task_id){
      setTaskId(data.task_id)
      startStream(data.task_id)
    } else {
      setStatus('error')
    }
  }

  const startStream = (id) => {
    if(eventRef.current) eventRef.current.close()
    const es = new EventSource(`/api/stream/${id}`)
    eventRef.current = es

    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        const { step, data } = msg
        if(step === 'done'){
          setStreamDone(true)
          // fetch final state for artifacts
          fetch(`/api/tasks/${id}`).then(r=>r.json()).then(d=>{
            setStatus(d.status)
            setArtifacts(d.state?.artifacts || [])
            setReview(d.state?.review || null)
            setLogs(d.state?.logs || [])
            setCurrentStep(d.state?.current_step || 'human_approval')
          })
          es.close()
          return
        }
        if(step === 'log'){
          setLogs(prev=>[...prev, data])
        } else {
          // node update
          setCurrentStep(step)
          if(data?.logs) setLogs(data.logs)
          if(data?.artifacts) setArtifacts(data.artifacts)
          if(data?.review) setReview(data.review)
          // also push node name as log
          setLogs(prev=>[...prev, `${step}: updated`])
        }
      } catch(err){
        console.error('parse', err)
      }
    }
    es.onerror = () => {
      // fallback fetch
      fetch(`/api/tasks/${id}`).then(r=>r.json()).then(d=>{
        if(d.status !== 'running'){
          setStreamDone(true)
          setStatus(d.status)
          setArtifacts(d.state?.artifacts || [])
          setReview(d.state?.review || null)
          es.close()
        }
      })
    }
  }

  const handleApprove = async (decision) => {
    if(!taskId) return
    const res = await fetch(`/api/tasks/${taskId}/approve`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ decision })
    })
    const d = await res.json()
    setStatus(d.status)
    if(d.pr) setReview(prev=>({...prev, pr: d.pr}))
  }

  const isAwaitingApproval = status === 'awaiting_approval' || (streamDone && currentStep==='human_approval')

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-sky-500 flex items-center justify-center text-white font-semibold text-sm">⟁</div>
            <div>
              <h1 className="text-sm font-semibold text-slate-900 leading-none">ForgeMind</h1>
              <p className="text-xs text-slate-500">Autonomous AI Software Engineering Agent · LangGraph · Gemini · RAG</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden sm:flex rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs">
              <button onClick={()=>setActiveTab('workflow')} className={`px-3 py-1.5 rounded-md font-medium ${activeTab==='workflow' ? 'bg-white border border-slate-200 text-slate-900 shadow-sm' : 'text-slate-500'}`}>Workflow</button>
              <button onClick={()=>{setActiveTab('benchmark'); fetch('/api/evaluation/results').then(r=>r.json()).then(setBench).catch(()=>{}); fetch('/api/rag/stats').then(r=>r.json()).then(setRagStats).catch(()=>{})}} className={`px-3 py-1.5 rounded-md font-medium ${activeTab==='benchmark' ? 'bg-white border border-slate-200 text-slate-900 shadow-sm' : 'text-slate-500'}`}>Benchmark</button>
            </div>
            <div className="text-xs text-slate-500 flex items-center gap-2 ml-2">
              <span className={`w-2 h-2 rounded-full ${health?.mock_mode ? 'bg-amber-400' : health?.status==='ok' ? 'bg-emerald-500' : 'bg-slate-300'}`}></span>
              {health?.mock_mode ? 'mock mode' : health?.status || 'checking...'}
              <a href="/docs" target="_blank" className="ml-2 text-sky-600 hover:text-sky-700">API Docs</a>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {activeTab==='benchmark' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-sm font-semibold text-slate-900">15-task Benchmark</h2>
              <p className="text-xs text-slate-500 mt-1">Own synthetic data + dataset.json. RAG {ragStats?.fallback_used ? 'fallback (keyword)' : 'vector'} · {ragStats?.chunks || 0} chunks</p>
              {!bench || bench.total===0 ? (
                <div className="mt-4 text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-4">No results yet. Run <code className="bg-white border px-1 rounded">python -m evaluation.evaluator 5</code> or <code>python evaluation/synthetic_generator.py; python -m evaluation.evaluator 15</code></div>
              ) : (
                <>
                  <div className="mt-4 grid grid-cols-4 gap-3">
                    <div className="rounded-xl bg-slate-50 border border-slate-200 p-3"><div className="text-xs text-slate-500">Completion</div><div className="text-lg font-semibold text-slate-900">{bench.task_completion}%</div></div>
                    <div className="rounded-xl bg-slate-50 border border-slate-200 p-3"><div className="text-xs text-slate-500">Tests pass</div><div className="text-lg font-semibold text-emerald-600">{bench.test_pass_rate}%</div></div>
                    <div className="rounded-xl bg-sky-50 border border-sky-200 p-3"><div className="text-xs text-sky-700">Avg latency</div><div className="text-lg font-semibold text-sky-700">{bench.avg_latency_sec}s</div></div>
                    <div className="rounded-xl bg-slate-50 border border-slate-200 p-3"><div className="text-xs text-slate-500">Total</div><div className="text-lg font-semibold text-slate-900">{bench.total} / {bench.mock_mode ? 'mock' : 'real'}</div></div>
                  </div>
                  <div className="mt-4 overflow-auto rounded-lg border border-slate-200">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-3 py-2 font-medium">Task</th><th className="px-3 py-2">Tests</th><th className="px-3 py-2">Review</th><th className="px-3 py-2">Latency</th><th className="px-3 py-2">Success</th></tr></thead>
                      <tbody>
                        {bench.results?.map(r=>(
                          <tr key={r.id} className="border-t border-slate-100"><td className="px-3 py-2 font-medium text-slate-900">{r.id} {r.title}</td><td className={`px-3 py-2 text-center ${r.tests_passed ? 'text-emerald-600' : 'text-amber-600'}`}>{r.tests_passed ? '✓' : '✗'}</td><td className="px-3 py-2 text-center">{r.review_decision}</td><td className="px-3 py-2 text-center">{r.latency_sec}s</td><td className="px-3 py-2 text-center">{r.success ? '✓' : '✗'}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <button onClick={()=>fetch('/api/evaluation/results').then(r=>r.json()).then(setBench)} className="mt-3 text-xs text-sky-600 hover:text-sky-700">Refresh</button>
                </>
              )}
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="text-sm font-medium text-slate-900">Tabular RAG — No Hallucination</h3>
              <p className="text-xs text-slate-500 mt-1">ForgeMind preserves tables with header repetition + metadata. Try uploading your CSV.</p>
              <div className="mt-3 flex items-center gap-3">
                <input type="file" accept=".csv,.tsv,.md,.txt,.json" onChange={async (e)=>{
                  const file=e.target.files[0]; if(!file) return;
                  const form=new FormData(); form.append('file', file);
                  const res=await fetch('/api/rag/ingest', {method:'POST', body: form});
                  const data=await res.json();
                  alert(data.status ? `Ingested ${data.file}: ${data.chunks} chunks` : `Error: ${data.error}`);
                  fetch('/api/rag/stats').then(r=>r.json()).then(setRagStats).catch(()=>{})
                }} className="text-xs file:mr-3 file:rounded-lg file:border-0 file:bg-sky-500 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-sky-600" />
                <span className="text-xs text-slate-500">or</span>
                <button onClick={async ()=>{
                  const q=prompt('Query tabular data e.g. What is Alice Johnson salary?');
                  if(!q) return;
                  const res=await fetch(`/api/rag/query?q=${encodeURIComponent(q)}`);
                  const data=await res.json();
                  alert(data.context ? data.context.slice(0,800) : JSON.stringify(data))
                }} className="text-xs rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50">Test Query</button>
              </div>
              <div className="mt-3 rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-800">
                ✓ CSV/MD tables chunked with header repetition: <code>Columns: id, name, email...</code> + <code>Rows 0-19</code> + linearized rows. Retrieval preserves 2000 chars for tables vs 800 for text.
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="text-sm font-medium text-slate-900">Synthetic own data</h3>
              <p className="text-xs text-slate-500 mt-1">Generate diverse tasks beyond CRUD clones, then benchmark.</p>
              <pre className="mt-3 bg-slate-900 text-slate-100 rounded-lg p-3 text-xs overflow-auto">python evaluation/synthetic_generator.py --count 5
python -m rag.ingestion   # re-ingest docs_seed + synthetic (7 chunks: 5 text, 2 table)
python -m evaluation.evaluator 15</pre>
            </div>
          </div>
        )}
        {activeTab==='workflow' && (
        <>
        {/* Task input */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <label className="text-sm font-medium text-slate-700">Task</label>
          <textarea
            value={request}
            onChange={e=>setRequest(e.target.value)}
            rows={4}
            className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
            placeholder="Describe what to build..."
          />
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-slate-500">Gemini Flash/Pro via LLMProvider · Chroma RAG · LangGraph</span>
            <button
              onClick={startTask}
              disabled={status==='running'}
              className="inline-flex items-center rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
            >
              {status==='running' ? 'Running...' : 'Start Task'}
            </button>
          </div>
        </div>

        {/* Progress */}
        {(taskId || status==='running') && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-semibold text-slate-900">Workflow</h2>
              <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                {taskId ? taskId.slice(0,8) : ''} · {status}
              </span>
            </div>
            <Stepper current={currentStep} logs={logs} done={streamDone} />

            {logs.length>0 && (
              <div className="mt-6 rounded-lg bg-slate-900 text-slate-100 p-4 text-xs font-mono max-h-40 overflow-auto">
                {logs.map((l,i)=><div key={i} className="text-slate-300">› {l}</div>)}
              </div>
            )}

            {artifacts.length>0 && (
              <div className="mt-6">
                <h3 className="text-sm font-medium text-slate-700">Artifacts · {artifacts.length} files</h3>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {artifacts.map((a,i)=>(
                    <div key={i} className="text-xs px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-slate-600 truncate">{a}</div>
                  ))}
                </div>
              </div>
            )}

            {isAwaitingApproval && (
              <div className="mt-6 rounded-xl border border-sky-200 bg-sky-50 p-5">
                <h3 className="text-sm font-semibold text-slate-900">Human Approval Required</h3>
                <p className="text-xs text-slate-600 mt-1">Review artifacts and approve to create GitHub PR (dry-run if no token).</p>
                {review && (
                  <div className="mt-3 text-xs text-slate-600 bg-white border border-slate-200 rounded-lg p-3">
                    <div><span className="font-medium">Review:</span> {review.decision} · score {review.score}/10</div>
                    {review.issues?.length>0 && <div className="mt-1">Issues: {review.issues.join('; ')}</div>}
                  </div>
                )}
                <div className="mt-4 flex gap-3">
                  <button onClick={()=>handleApprove('rejected')} className="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50">Reject</button>
                  <button onClick={()=>handleApprove('approved')} className="flex-1 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-sky-600">Approve & Create PR</button>
                </div>
              </div>
            )}

            {status==='completed' && (
              <div className="mt-6 rounded-lg bg-emerald-50 border border-emerald-200 p-4 text-sm text-emerald-800">✓ Completed & approved. {review?.pr?.status === 'dry_run' ? 'Dry-run - artifacts ready locally.' : review?.pr?.pr_url || ''}</div>
            )}
            {status==='rejected' && <div className="mt-6 rounded-lg bg-amber-50 border border-amber-200 p-4 text-sm text-amber-800">Rejected - awaiting revision.</div>}
          </div>
        )}

        {/* Info */}
        <div className="grid grid-cols-3 gap-4 text-xs">
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="font-medium text-slate-900">Orchestration</div>
            <div className="text-slate-500 mt-1">LangGraph state, branches, retries, HITL</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="font-medium text-slate-900">Grounded</div>
            <div className="text-slate-500 mt-1">Chroma RAG over docs_seed</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="font-medium text-slate-900">Verified</div>
            <div className="text-slate-500 mt-1">pytest → fix → rerun, reviewer</div>
          </div>
        </div>
        </>
        )}
      </main>

      <footer className="max-w-3xl mx-auto px-6 py-8 text-center text-xs text-slate-400">
        ForgeMind © 2026 · LangGraph · Gemini · RAG · Multi-Agent · Human-in-the-Loop · Scales to Docker · pgvector · Custom Orchestration
      </footer>
    </div>
  )
}
