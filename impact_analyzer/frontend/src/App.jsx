import { useState, useEffect } from 'react'
import ImpactAnalyzer from './components/ImpactAnalyzer'
import { sendMessage, clearUpload, getBedrockStatus, analyzeIntegration, clearIntegration } from './services/api'
import './App.css'

export default function App() {
  const [isLoading, setIsLoading]                   = useState(false)
  const [impactResult, setImpactResult]             = useState(null)
  const [impactConfigStats, setImpactConfigStats]   = useState(null)
  const [releaseStats, setReleaseStats]             = useState(null)
  const [resetKey, setResetKey]                     = useState(0)
  const [bedrockConfigured, setBedrockConfigured]   = useState(false)
  const [integrationStats, setIntegrationStats]     = useState(null)
  const [integrationResult, setIntegrationResult]   = useState(null)
  const [integrationLoading, setIntegrationLoading] = useState(false)

  useEffect(() => {
    getBedrockStatus().then(s => setBedrockConfigured(!!s.configured))
  }, [])

  async function handleSend(text) {
    setIsLoading(true)
    try {
      const result = await sendMessage(text, 'impact', [])
      setImpactResult(result.response)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      setImpactResult(`⚠️ Error: ${detail}`)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleUploadComplete(msg, success = false, sheetStats = null) {
    if (success) {
      if (sheetStats?.length > 0) setImpactConfigStats(sheetStats)
      if (releaseStats) await handleSend('run impact analysis')
    }
  }

  async function handleReleaseUploadComplete(msg, success = false, sheetStats = null) {
    if (success) {
      if (sheetStats?.length > 0) setReleaseStats(sheetStats)
      if (impactConfigStats) await handleSend('run impact analysis')
    }
  }

  async function handleIntegrationUploadComplete(msg, success = false, sheetStats = null) {
    if (success && sheetStats?.length > 0) {
      setIntegrationStats(sheetStats)
    }
  }

  async function handleRunIntegrationAnalysis() {
    setIntegrationLoading(true)
    try {
      const result = await analyzeIntegration()
      setIntegrationResult(result.report)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      setIntegrationResult(`⚠️ Error: ${detail}`)
    } finally {
      setIntegrationLoading(false)
    }
  }

  async function handleClear() {
    setImpactResult(null)
    setImpactConfigStats(null)
    setReleaseStats(null)
    setIntegrationStats(null)
    setIntegrationResult(null)
    setResetKey((k) => k + 1)
    try { await clearUpload('impact') }       catch (_) {}
    try { await clearUpload('release') }      catch (_) {}
    try { await clearIntegration() }          catch (_) {}
  }

  return (
    <div className="app-layout">
      <div className="main-panel">
        <header className="header">
          <div className="header-left">
            <h1 className="header-title">🔍 Impact Analyzer</h1>
            <span className="header-sub">Analyse Veeva release changes and see what impacts your Vault config</span>
          </div>
          <button className="clear-btn" onClick={handleClear} title="Clear">🗑 Clear</button>
        </header>
        <ImpactAnalyzer
          key={resetKey}
          onUploadComplete={handleUploadComplete}
          onReleaseUploadComplete={handleReleaseUploadComplete}
          onIntegrationUploadComplete={handleIntegrationUploadComplete}
          onRunIntegrationAnalysis={handleRunIntegrationAnalysis}
          isLoading={isLoading}
          result={impactResult}
          releaseLoaded={releaseStats !== null}
          configLoaded={impactConfigStats !== null}
          integrationLoaded={integrationStats !== null}
          integrationLoading={integrationLoading}
          integrationResult={integrationResult}
          bedrockConfigured={bedrockConfigured}
        />
      </div>
    </div>
  )
}
