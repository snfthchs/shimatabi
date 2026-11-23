import type { InputHTMLAttributes } from 'react'

type Props = {
  id: string
  label: string
  error?: string
  hint?: string
} & InputHTMLAttributes<HTMLInputElement>

// ラベルつきの入力欄。エラーは、欄の下に、赤い文字で出す（色だけに頼らず、文章で伝える）。
export default function TextField({ id, label, error, hint, ...input }: Props) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-800">
        {label}
        <span className="ml-2 rounded bg-red-50 px-1.5 py-0.5 text-xs text-red-700">必須</span>
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`min-h-11 w-full rounded-lg border px-3 text-base text-slate-900 focus:outline-2 focus:outline-offset-1 focus:outline-teal-600 ${
          error ? 'border-red-500 bg-red-50' : 'border-slate-300 bg-white'
        }`}
        {...input}
      />
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
