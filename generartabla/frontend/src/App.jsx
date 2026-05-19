import { useState } from 'react'

export default function App() {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [tableUrl, setTableUrl] = useState('')

  const handleGenerateTable = async () => {
    setLoading(true)
    setMessage('')
    setTableUrl('')
    try {
      const r = await fetch('/api/generate-table', { method: 'POST' })
      const data = await r.json()
      if (data.status === 'success') {
        setMessage('Tabla generada exitosamente')
        setTableUrl('/api/table-image?t=' + Date.now())
      } else {
        setMessage(`Error: ${data.message}`)
      }
    } catch (e) {
      setMessage(`Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1>Generador de Tabla</h1>
      <button onClick={handleGenerateTable} disabled={loading}>
        {loading ? 'Generando...' : 'Generar Tabla'}
      </button>
      {message && <p className="message">{message}</p>}
      {tableUrl && (
        <div className="table-container">
          <img src={tableUrl} alt="Tabla de ranking" />
        </div>
      )}
    </div>
  )
}
