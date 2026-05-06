import { useEffect, useState } from 'react'

export default function TeamMultiSelect({ value, onChange }) {
  const [teams, setTeams] = useState([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/teams')
      .then(r => r.json())
      .then(d => { setTeams(d || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const toggle = (t) => {
    const exists = value.find(v => v.usernumber === t.usernumber)
    if (exists) onChange(value.filter(v => v.usernumber !== t.usernumber))
    else onChange([...value, { usernumber: t.usernumber, fullname: t.userfullname }])
  }

  const filtered = teams.filter(t =>
    !filter || (t.userfullname || '').toLowerCase().includes(filter.toLowerCase())
  )

  if (loading) return <p>Cargando equipos...</p>

  return (
    <div className="team-select">
      <input
        type="text" placeholder="Buscar equipo..."
        value={filter} onChange={e => setFilter(e.target.value)}
        className="form-input"
      />
      <div className="team-list">
        {filtered.slice(0, 50).map(t => {
          const checked = !!value.find(v => v.usernumber === t.usernumber)
          return (
            <label key={t.usernumber} className={`team-item ${checked ? 'checked' : ''}`}>
              <input type="checkbox" checked={checked} onChange={() => toggle(t)} />
              <span>{t.userfullname} ({t.country})</span>
            </label>
          )
        })}
      </div>
      <p className="muted">Seleccionados: {value.length}</p>
    </div>
  )
}
