import { useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import FileUpload from './FileUpload'
import ReleaseUpload from './ReleaseUpload'
import IntegrationUpload from './IntegrationUpload'
import QAChat from './QAChat'

const HOW_IT_WORKS = [
  {
    step: '1',
    icon: '📋',
    title: 'Parse Release Doc',
    desc: "Reads the '…Updates' sheet and extracts every changed component — its API name, type, change action, and whether it requires manual configuration.",
  },
  {
    step: '2',
    icon: '⚙️',
    title: 'Parse Config Report',
    desc: 'Scans every sheet of your Vault Config Report and extracts all Vault API names — objects, fields, layouts, integrations.',
  },
  {
    step: '3',
    icon: '🔗',
    title: 'Stage 1 Impact Report',
    desc: 'Cross-references both files. Flags High, Medium, Integration, Risk, and Config Change items — only where real overlap exists.',
  },
  {
    step: '4',
    icon: '🔌',
    title: 'Stage 2 Integration Analysis',
    desc: 'Upload your Integration Spec to cross-reference the impact report against each named integration. Critical, High, Review classification per integration.',
  },
]

function ResizableResults({ headerClass = '', headerContent, bodyClass = '', children }) {
  const [height, setHeight] = useState(460)
  const dragging = useRef(false)
  const startY   = useRef(0)
  const startH   = useRef(0)

  function onMouseDown(e) {
    e.preventDefault()
    dragging.current = true
    startY.current   = e.clientY
    startH.current   = height

    function onMove(ev) {
      if (!dragging.current) return
      const next = Math.max(160, Math.min(window.innerHeight * 0.92, startH.current + ev.clientY - startY.current))
      setHeight(next)
    }
    function onUp() {
      dragging.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div className="ia-results" style={{ height }}>
      <div className={`ia-results-header ${headerClass}`}>
        {headerContent}
      </div>
      <div className={`ia-results-body ${bodyClass}`}>
        {children}
      </div>
      <div className="ia-resize-handle" onMouseDown={onMouseDown} title="Drag to resize" />
    </div>
  )
}

export default function ImpactAnalyzer({
  onUploadComplete,
  onReleaseUploadComplete,
  onIntegrationUploadComplete,
  onRunIntegrationAnalysis,
  isLoading,
  result,
  releaseLoaded,
  configLoaded,
  integrationLoaded,
  integrationLoading,
  integrationResult,
  bedrockConfigured,
}) {
  const showStage2  = !!result
  const showQA      = !!result

  return (
    <div className="ia-root">

      {/* ── Page header ──────────────────────────────────── */}
      <div className="ia-page-header">
        <div className="ia-page-header-left">
          <span className="ia-page-icon">🔍</span>
          <div>
            <h2 className="ia-page-title">Release Impact Analyzer</h2>
            <p className="ia-page-sub">
              Upload both documents — the tool cross-references them and shows exactly
              what in your Vault configuration is affected by the new release.
            </p>
          </div>
        </div>
        <div className="ia-badges">
          <span className={`ia-badge ${releaseLoaded ? 'ia-badge-ok' : 'ia-badge-pending'}`}>
            {releaseLoaded ? '✓ Release Doc' : '○ Release Doc'}
          </span>
          <span className={`ia-badge ${configLoaded ? 'ia-badge-ok' : 'ia-badge-pending'}`}>
            {configLoaded ? '✓ Config Report' : '○ Config Report'}
          </span>
          <span className={`ia-badge ${integrationLoaded ? 'ia-badge-ok' : 'ia-badge-pending'}`}>
            {integrationLoaded ? '✓ Integration Spec' : '○ Integration Spec'}
          </span>
          <span
            className={`ia-badge ${bedrockConfigured ? 'ia-badge-ai' : 'ia-badge-ai-off'}`}
            title={bedrockConfigured
              ? 'Amazon Bedrock active — AI-enhanced reports and Q&A enabled'
              : 'Add AWS credentials to .env to enable AI-enhanced reports and Q&A'}
          >
            {bedrockConfigured ? '✦ AI Enhanced' : '○ AI Enhanced'}
          </span>
        </div>
      </div>

      {/* ── Stage 1 upload row ───────────────────────────── */}
      <div className="ia-section-label">Stage 1 — Impact Analysis</div>
      <div className="ia-upload-row">
        <div className="ia-upload-card">
          <div className="ia-upload-card-header">
            <span className="ia-upload-card-icon">📋</span>
            <div>
              <div className="ia-upload-card-title">Data Model Change Document</div>
              <div className="ia-upload-card-hint">e.g. 26R1 RIM Data Model Changes.xlsx / .pdf / .docx</div>
            </div>
          </div>
          <ReleaseUpload onUploadComplete={onReleaseUploadComplete} />
        </div>

        <div className="ia-upload-plus">+</div>

        <div className="ia-upload-card">
          <div className="ia-upload-card-header">
            <span className="ia-upload-card-icon">⚙️</span>
            <div>
              <div className="ia-upload-card-title">Vault Configuration Report</div>
              <div className="ia-upload-card-hint">Your Vault config export (.xlsx / .pdf / .csv / .docx)</div>
            </div>
          </div>
          <FileUpload purpose="impact" onUploadComplete={onUploadComplete} />
        </div>
      </div>

      {/* ── Stage 1 loading ──────────────────────────────── */}
      {isLoading && (
        <div className="ia-loading">
          <div className="ia-loading-spinner" />
          <span>Analysing release changes against your configuration…</span>
        </div>
      )}

      {/* ── Stage 1 results ──────────────────────────────── */}
      {result && !isLoading && (
        <ResizableResults
          headerContent={<><span>📊</span><strong>Stage 1 — Impact Report</strong></>}
          bodyClass="markdown-body"
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
            {result}
          </ReactMarkdown>
        </ResizableResults>
      )}

      {/* ── Stage 2 ──────────────────────────────────────── */}
      {showStage2 && (
        <>
          <div className="ia-section-label">Stage 2 — Integration Specification Analysis</div>
          <div className="ia-upload-card ia-stage2-card">
            <div className="ia-upload-card-header">
              <span className="ia-upload-card-icon">🔌</span>
              <div>
                <div className="ia-upload-card-title">Integration Specification Document</div>
                <div className="ia-upload-card-hint">
                  Your integration spec listing integration names, source/target systems, and Vault API fields (.xlsx / .csv / .pdf / .docx)
                </div>
              </div>
            </div>
            <div className="ia-stage2-row">
              <IntegrationUpload onUploadComplete={onIntegrationUploadComplete} />
              <button
                className="ia-run-btn"
                disabled={!integrationLoaded || integrationLoading}
                onClick={onRunIntegrationAnalysis}
              >
                {integrationLoading
                  ? <><span className="upload-spinner" /> Analysing…</>
                  : '▶ Run Integration Analysis'}
              </button>
            </div>
          </div>

          {/* Stage 2 results */}
          {integrationResult && !integrationLoading && (
            <ResizableResults
              headerClass="ia-results-header-stage2"
              headerContent={<><span>🔌</span><strong>Stage 2 — Integration Analysis Report</strong></>}
              bodyClass="markdown-body"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                {integrationResult}
              </ReactMarkdown>
            </ResizableResults>
          )}
        </>
      )}

      {/* ── Q&A Chat ─────────────────────────────────────── */}
      {showQA && (
        <QAChat bedrockConfigured={bedrockConfigured} />
      )}

      {/* ── How it works (shown before first analysis) ───── */}
      {!result && !isLoading && (
        <div className="ia-howto">
          <div className="ia-howto-title">How the analysis works</div>
          <div className="ia-howto-grid">
            {HOW_IT_WORKS.map((h) => (
              <div key={h.step} className="ia-howto-card">
                <div className="ia-howto-step">{h.step}</div>
                <div className="ia-howto-icon">{h.icon}</div>
                <div className="ia-howto-card-title">{h.title}</div>
                <p className="ia-howto-card-desc">{h.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}
