import { useState } from 'react'
import { useTheme } from '../theme/ThemeContext'
import { MASCOT } from '../brand'

interface BrandMarkProps {
  className?: string
  alt?: string
  title?: string
}

/** Mascot only: the classic Caesar, or the glowing Count in Halloween mode. */
export default function BrandMark({ className = '', alt = 'Little Caesars', title }: BrandMarkProps) {
  const { isHalloween } = useTheme()
  const [failed, setFailed] = useState(false)

  if (isHalloween && !failed) {
    return (
      <img
        src={MASCOT.halloween}
        alt={alt}
        title={title ?? 'Count Little Caesars'}
        className={`count-glow ${className}`}
        onError={() => setFailed(true)}
      />
    )
  }

  return <img src={MASCOT.default} alt={alt} title={title} className={className} />
}

/**
 * Header lockup. Light: the official mascot + wordmark lockup, unchanged.
 * Halloween: the glowing Count takes the mascot's place next to the wordmark.
 */
export function BrandLockup({ height = 'h-8', countHeight = 'h-12' }: { height?: string; countHeight?: string }) {
  const { isHalloween } = useTheme()

  if (!isHalloween) {
    return <img src="/lc-logo.svg" alt="Little Caesars" className={`${height} mix-blend-multiply`} />
  }

  return (
    <div className="flex items-center gap-2">
      <BrandMark className={`${countHeight} w-auto -my-2`} />
      <img src="/lc-wordmark.svg" alt="" aria-hidden="true" className={height === 'h-8' ? 'h-6' : 'h-10'} />
    </div>
  )
}
