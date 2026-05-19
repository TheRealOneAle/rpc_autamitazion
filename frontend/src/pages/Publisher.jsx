import { useState, useEffect, useRef } from 'react'

const API = '/ms4-api'

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })
}

function buildDescription(data, config) {
  const competitionName  = config.competition_name  || 'Competencia RPC 2026'
  const totalSubmissions = data.total_submissions   ?? '?'
  const teamsWithSolved  = data.teams_with_solved   ?? '?'
  const totalTeams       = data.total_teams         ?? '?'
  return (
    `Asi quedo la parte alta del tablero FINAL de la ${competitionName}. ` +
    `Se realizaron en total ${totalSubmissions} envios, donde ${teamsWithSolved} equipos ` +
    `(de ${totalTeams} en competencia) ` +
    `#TodosSomosRPC #CreciendoTodosJuntos`
  )
}

export default function Publisher() {
  const [status, setStatus]         = useState(null)
  const [statusErr, setStatusErr]   = useState(false)
  const [preview, setPreview]       = useState({ body: 'Cargando vista previa...', pageName: 'RPC Competencia', note: '' })
  const [imgSrc, setImgSrc]         = useState('')
  const [imgVisible, setImgVisible] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [publishMsg, setPublishMsg] = useState({ text: '', err: false })
  const [pageId, setPageId]         = useState('')
  const [token, setToken]           = useState('')
  const [tokenMsg, setTokenMsg]     = useState({ text: '', err: false })

  async function loadStatus() {
    try {
      const r = await fetch(`${API}/api/status/`)
      const d = await r.json()
      setStatus(d)
      setStatusErr(false)
    } catch {
      setStatusErr(true)
    }
  }

  async function loadPreview() {
    const configMap = {}
    try {
      const r = await fetch(`${API}/api/config/`)
      const cfgs = await r.json()
      cfgs.forEach(c => { configMap[c.key] = c.value })
    } catch (_) {}

    try {
      const r = await fetch(`${API}/api/competition-stats/`)
      const stats = await r.json()
      if (stats.error) throw new Error(stats.error)
      setPreview({
        body: buildDescription(stats, configMap),
        pageName: configMap.competition_name || 'RPC Competencia',
        note: 'Vista previa con datos actuales de la competencia.',
      })
    } catch {
      setPreview({
        body: buildDescription({ total_teams: 173, total_submissions: 1335, teams_with_solved: 153 }, configMap),
        pageName: configMap.competition_name || 'RPC Competencia',
        note: 'No se pudieron obtener datos de la BD. Mostrando ejemplo.',
      })
    }
  }

  function refreshImage() {
    setImgSrc(`${API}/api/preview-image/?t=${Date.now()}`)
    setImgVisible(false)
  }

  useEffect(() => {
    loadStatus()
    loadPreview()
    refreshImage()
    const t1 = setInterval(loadStatus, 10000)
    const t2 = setInterval(loadPreview, 30000)
    const t3 = setInterval(refreshImage, 30000)
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3) }
  }, [])

  async function handlePublish() {
    setPublishing(true)
    setPublishMsg({ text: '', err: false })
    try {
      const r = await fetch(`${API}/api/trigger/`, { method: 'POST' })
      const d = await r.json()
      if (r.ok) {
        setPublishMsg({ text: d.detail || 'Ciclo iniciado en segundo plano', err: false })
        setTimeout(() => { loadStatus(); loadPreview() }, 3000)
      } else {
        setPublishMsg({ text: d.detail || 'Error al publicar', err: true })
      }
    } catch {
      setPublishMsg({ text: 'Error de conexion con el servicio', err: true })
    } finally {
      setPublishing(false)
    }
  }

  async function handleSaveToken() {
    if (!pageId || !token) {
      setTokenMsg({ text: 'Completa el Page ID y el token', err: true })
      return
    }
    setTokenMsg({ text: 'Guardando...', err: false })
    try {
      const r = await fetch(`${API}/api/token/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page_id: pageId, access_token: token }),
      })
      const d = await r.json()
      if (r.ok) {
        setTokenMsg({ text: 'Token guardado correctamente', err: false })
        setToken('')
      } else {
        setTokenMsg({ text: JSON.stringify(d), err: true })
      }
    } catch {
      setTokenMsg({ text: 'Error de conexion', err: true })
    }
  }

  const dotClass = (active) => `pub-dot ${active ? 'on' : 'off'}`

  return (
    <div className="pub-page">
      <div className="pub-header">
        <h1 className="pub-title">Automatizador de Publicaciones</h1>
        <p className="pub-subtitle">Vista previa y control de publicaciones en Facebook</p>
      </div>

      <div className="pub-grid">
        <div className="pub-col">

          <div className="pub-card">
            <h2 className="pub-card-title">Estado del servicio</h2>
            <div className="pub-status-row">
              <span className={dotClass(status?.proceso_activo)} />
              <span className="pub-status-label">
                {statusErr ? 'Sin conexion con el servicio' : (status?.proceso_activo ? 'Proceso activo' : 'Proceso inactivo')}
              </span>
            </div>
            <div className="pub-status-row">
              <span className={dotClass(status?.scheduler_running)} />
              <span className="pub-status-label">
                {status?.scheduler_running ? 'Scheduler corriendo' : 'Scheduler detenido'}
              </span>
            </div>
            {status?.next_run && (
              <p className="pub-next-run">Proxima ejecucion: {fmt(status.next_run)}</p>
            )}
            <button
              className="pub-btn-publish"
              disabled={publishing || !status}
              onClick={handlePublish}
            >
              {publishing ? 'Publicando...' : 'Publicar ahora'}
            </button>
            {publishMsg.text && (
              <p className={`pub-msg${publishMsg.err ? ' err' : ''}`}>{publishMsg.text}</p>
            )}
          </div>

          <div className="pub-card">
            <h2 className="pub-card-title">Token de Facebook</h2>
            <p className="pub-token-help">
              Necesitas un <strong>Page Access Token</strong> con el permiso{' '}
              <code>pages_manage_posts</code>. Obtenlo en el{' '}
              <a href="https://developers.facebook.com/tools/explorer/" target="_blank" rel="noreferrer">
                Graph API Explorer
              </a>: selecciona tu app, luego tu pagina y genera el token.
            </p>
            <div className="pub-token-form">
              <div>
                <label className="pub-token-label">Page ID</label>
                <input
                  className="pub-token-input"
                  type="text"
                  placeholder="123456789012345"
                  value={pageId}
                  onChange={e => setPageId(e.target.value)}
                />
              </div>
              <div>
                <label className="pub-token-label">Page Access Token</label>
                <textarea
                  className="pub-token-input"
                  rows={3}
                  placeholder="EAABsbCS..."
                  value={token}
                  onChange={e => setToken(e.target.value)}
                />
              </div>
              <button className="pub-btn-token" onClick={handleSaveToken}>Guardar token</button>
              {tokenMsg.text && (
                <p className={`pub-msg${tokenMsg.err ? ' err' : ''}`}>{tokenMsg.text}</p>
              )}
            </div>
          </div>

        </div>

        <div className="pub-card pub-preview-card">
          <h2 className="pub-card-title">Vista previa del post</h2>

          <div className="fb-card">
            <div className="fb-header">
              <div className="fb-avatar">R</div>
              <div>
                <div className="fb-name">{preview.pageName}</div>
                <div className="fb-meta">Ahora · Publico</div>
              </div>
            </div>

            {!imgVisible && (
              <div className="fb-img-placeholder">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#1877f2" strokeWidth="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <path d="M21 15l-5-5L5 21"/>
                </svg>
                <span>Cargando imagen del ranking...</span>
              </div>
            )}
            {imgSrc && (
              <img
                src={imgSrc}
                alt="Ranking"
                style={{ display: imgVisible ? 'block' : 'none', width: '100%', borderBottom: '1px solid #eee' }}
                onLoad={() => setImgVisible(true)}
                onError={() => setImgVisible(false)}
              />
            )}

            <div className="fb-body">{preview.body}</div>
            <div className="fb-reactions">
              <span>Me gusta</span>
              <span>Comentar</span>
              <span>Compartir</span>
            </div>
          </div>

          {preview.note && <p className="pub-preview-note">{preview.note}</p>}
        </div>
      </div>
    </div>
  )
}
