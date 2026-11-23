// APIを呼ぶ共通の関数。エラーは、APIが返す統一した形（`{"error": {"code", "message", "details"}}`）で扱う。

export type ErrorDetail = { field: string; type: string }

export class ApiError extends Error {
  status: number
  code: string
  details: ErrorDetail[]

  constructor(status: number, code: string, message: string, details: ErrorDetail[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function readError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json()
    const error = (body as { error?: { code?: unknown; message?: unknown; details?: unknown } })
      ?.error
    if (error && typeof error.code === 'string') {
      return new ApiError(
        response.status,
        error.code,
        typeof error.message === 'string' ? error.message : '',
        Array.isArray(error.details) ? (error.details as ErrorDetail[]) : [],
      )
    }
  } catch {
    // JSONではない応答は、下の既定のエラーにする
  }
  return new ApiError(response.status, 'UNKNOWN', 'エラーが発生しました。もう一度お試しください。')
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'NETWORK', '通信できませんでした。電波の状態を確認して、もう一度お試しください。')
  }
  if (!response.ok) {
    throw await readError(response)
  }
  return (await response.json()) as T
}

type QueryValue = string | number | boolean | null | undefined

/** 検索条件から、`?a=1&b=true` の形の文字列を作る。空・未指定・false は、含めない。 */
export function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) {
      continue
    }
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}
