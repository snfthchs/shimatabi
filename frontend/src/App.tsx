import { useEffect, useState } from 'react'

type HealthState = 'checking' | 'ok' | 'error'

const healthLabels: Record<HealthState, string> = {
  checking: '確認中…',
  ok: 'つながっています',
  error: 'つながりません（バックエンドが起動しているか確認してください）',
}

// 雛形の疎通確認用の画面。Issue F・G で、旅行者・事業者の画面に置き換える。
function App() {
  const [health, setHealth] = useState<HealthState>('checking')

  useEffect(() => {
    const controller = new AbortController()

    fetch('/api/health', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`status ${response.status}`)
        }
        return response.json() as Promise<{ status: string }>
      })
      .then((body) => setHealth(body.status === 'ok' ? 'ok' : 'error'))
      .catch((error: unknown) => {
        // 画面を離れて中断したときは、状態を更新しない。
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setHealth('error')
      })

    return () => controller.abort()
  }, [])

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-bold">シマタビ（仮）</h1>
      <p className="text-sm text-slate-600">雛形の疎通確認ページです。</p>
      <p role="status" className="rounded-lg bg-slate-100 px-4 py-2 text-sm">
        APIとの接続: {healthLabels[health]}
      </p>
    </main>
  )
}

export default App
