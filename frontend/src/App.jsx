import { useState } from 'react'
import './App.css'

function App() {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [tableUrl, setTableUrl] = useState('')

  const handleGenerateTable = async () => {
    setLoading(true)
    setMessage('')
    setTableUrl('')

    try {
      const response = await fetch('/api/generate-table', {
        method: 'POST'
      })
      const data = await response.json()

      if (data.status === 'success') {
        setMessage('Tabla generada exitosamente')
        setTableUrl('/api/table-image')
      } else {
        setMessage(`Error: ${data.message}`)
      }
    } catch (error) {
      setMessage(`Error de conexión: ${error.message}`)
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
          <img src={tableUrl} alt="Tabla generada" />
        </div>
      )}
    </div>
  )
}

export default App
