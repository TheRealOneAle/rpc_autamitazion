import { useEffect, useRef, useState } from 'react'

export default function TeamMultiSelect({ value, onChange }) {
  const [teams, setTeams] = useState([])
  const [filter, setFilter] = useState('')
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const ref = useRef(null)

  useEffect(() => {
    fetch('/api/teams')
      .then(r => r.json())
      .then(d => { setTeams(d || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const toggle = (t) => {
    const exists = value.find(v => v.usernumber === t.usernumber)
    if (exists) onChange(value.filter(v => v.usernumber !== t.usernumber))
    else onChange([...value, { usernumber: t.usernumber, fullname: t.userfullname }])
  }

  const filtered = teams.filter(t =>
    !filter || (t.userfullname || '').toLowerCase().includes(filter.toLowerCase())
  )

  const label = loading
    ? 'Cargando equipos...'
    : value.length === 0
    ? 'Selecciona equipos...'
    : value.length === 1
    ? value[0].fullname
    : `${value.length} equipos seleccionados`

  return (
    <div className="ts-wrapper" ref={ref}>
      <button type="button" className={`ts-trigger ${open ? 'open' : ''}`} onClick={() => setOpen(o => !o)}>
        <span className="ts-label">{label}</span>
        <span className="ts-arrow">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="ts-dropdown">
          <input
            className="ts-search"
            type="text"
            placeholder="Buscar equipo..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            autoFocus
          />
          <div className="ts-list">
            {filtered.length === 0 && <p className="ts-empty">Sin resultados</p>}
            {filtered.map(t => {
              const checked = !!value.find(v => v.usernumber === t.usernumber)
              return (
                <label key={t.usernumber} className={`ts-item ${checked ? 'checked' : ''}`}>
                  <input type="checkbox" checked={checked} onChange={() => toggle(t)} />
                  <span>{t.userfullname} <span className="ts-country">({t.country})</span></span>
                </label>
              )
            })}
          </div>
          {value.length > 0 && (
            <div className="ts-footer">
              {value.length} seleccionado{value.length > 1 ? 's' : ''}
              <button type="button" className="ts-clear" onClick={() => onChange([])}>Limpiar</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
