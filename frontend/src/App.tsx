import { useEffect, useState } from 'react'

type Health = { status: string }

export function App() {
  const [status, setStatus] = useState<string>('проверяем...')
  const [ok, setOk] = useState<boolean | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json() as Promise<Health>)
      .then((data) => {
        setStatus(data.status)
        setOk(data.status === 'ok')
      })
      .catch(() => {
        setStatus('бэкенд недоступен')
        setOk(false)
      })
  }, [])

  return (
    <div className="card">
      <h1>Матчдей</h1>
      <p>
        Бэкенд отвечает:{' '}
        <span className={ok ? 'ok' : 'fail'}>{status}</span>
      </p>
    </div>
  )
}
