import { useState } from 'react'

type Props = { src: string; alt: string; className?: string }

// 体験の写真。読み込めなかったときは、色のついた枠に置き換える。
export default function Photo({ src, alt, className = '' }: Props) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div
        role="img"
        aria-label={alt}
        className={`bg-linear-to-br from-brand-100 to-sky-200 ${className}`}
      />
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`object-cover ${className}`}
    />
  )
}
