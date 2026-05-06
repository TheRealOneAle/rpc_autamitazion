import { useState } from 'react'
import TeamMultiSelect from '../components/TeamMultiSelect'

const PAISES = ['Colombia','Argentina','Brasil','Chile','México','Perú','Uruguay','Venezuela','Ecuador','Bolivia','Paraguay']

export default function CoachRegister() {
  const [form, setForm] = useState({
    nombre: '', apellido: '', login: '', password: '', password2: '',
    email: '', pais: 'Colombia', universidad: '', teams: [],
  })
  const [msg, setMsg] = useState(null)
  const [loading, setLoading] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setMsg(null)
    if (form.password !== form.password2) { setMsg({ ok: false, text: 'Las contraseñas no coinciden' }); return }
    if (form.teams.length === 0) { setMsg({ ok: false, text: 'Selecciona al menos un equipo' }); return }
    setLoading(true)
    try {
      const { password2, ...payload } = form
      const r = await fetch('/api/coaches', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await r.json()
      if (r.ok) setMsg({ ok: true, text: `Coach registrado (id: ${data.id})` })
      else setMsg({ ok: false, text: data.detail || 'Error al registrar' })
    } catch (err) { setMsg({ ok: false, text: err.message }) }
    finally { setLoading(false) }
  }

  return (
    <div className="register-container">
      <div className="register-grid">
        <section className="panel">
          <h2>Coach information</h2>
          <p className="muted">Please fill out the coach information</p>
          <p className="hint">fields with (*) are required</p>

          <label className="lbl">* Name</label>
          <input className="form-input" value={form.nombre} onChange={set('nombre')} required />

          <label className="lbl">* Last Name</label>
          <input className="form-input" value={form.apellido} onChange={set('apellido')} required />

          <label className="lbl">* Login</label>
          <input className="form-input" value={form.login} onChange={set('login')} required />

          <label className="lbl">* Email</label>
          <input className="form-input" type="email" value={form.email} onChange={set('email')} required />

          <label className="lbl">Password</label>
          <input className="form-input" type="password" value={form.password} onChange={set('password')} required />

          <label className="lbl">Password confirmation</label>
          <input className="form-input" type="password" value={form.password2} onChange={set('password2')} required />

          <label className="lbl">* Country</label>
          <select className="form-input" value={form.pais} onChange={set('pais')}>
            {PAISES.map(p => <option key={p}>{p}</option>)}
          </select>

          <label className="lbl">* University</label>
          <input className="form-input" value={form.universidad} onChange={set('universidad')} required />
        </section>

        <section className="panel">
          <h2>Teams' information</h2>
          <p className="muted">Selecciona los equipos de los que eres coach</p>
          <TeamMultiSelect
            value={form.teams}
            onChange={(teams) => setForm({ ...form, teams })}
          />
        </section>
      </div>

      <button className="btn-primary" onClick={submit} disabled={loading}>
        {loading ? 'Registrando...' : 'Create Coach'}
      </button>
      {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
    </div>
  )
}
