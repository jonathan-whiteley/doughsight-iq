import { motion, useReducedMotion } from 'framer-motion'
import { useTheme } from '../theme/ThemeContext'

const BAT_SVG = `<svg viewBox="0 0 56 20">
  <path fill="#0B0710" stroke="#B57BFF" stroke-width=".8" d="M1 9 C7 1 13 3 17 8 C19 5 21 4 24 5 L26 1 L28 5 L30 1 L32 5 C35 4 37 5 39 8 C43 3 49 1 55 9 C51 8 48 10 47 13 C44 10 41 11 39 14 C36 12 33 13 28 17 C23 13 20 12 17 14 C15 11 12 10 9 13 C8 10 5 8 1 9Z"/>
  <circle cx="26.5" cy="7" r=".9" fill="#FF6000"/>
  <circle cx="29.5" cy="7" r=".9" fill="#FF6000"/>
</svg>`

function CobWeb() {
  const angles = [0, 15, 32, 50, 68, 90].map(a => (a * Math.PI) / 180)
  let pathStr = ''

  // Radial spokes
  for (const a of angles) {
    pathStr += `<line x1="0" y1="0" x2="${230 * Math.cos(a)}" y2="${230 * Math.sin(a)}"/>`
  }

  // Sagging rings
  for (const r of [40, 75, 112, 150, 190]) {
    for (let i = 0; i < angles.length - 1; i++) {
      const [a, b] = [angles[i], angles[i + 1]]
      const m = (a + b) / 2
      const sag = r * 0.86
      pathStr += `<path d="M${r * Math.cos(a)} ${r * Math.sin(a)} Q${sag * Math.cos(m)} ${sag * Math.sin(m)} ${r * Math.cos(b)} ${r * Math.sin(b)}"/>`
    }
  }

  return (
    <svg className="w-full h-full" viewBox="0 0 230 230" dangerouslySetInnerHTML={{
      __html: `<g fill="none" stroke="#E8DCC8" stroke-width="1.2">${pathStr}</g>`
    }} />
  )
}

function Bat({ delay, size = 56, duration = 18 }: { delay: number; size?: number; duration?: number }) {
  const prefersReducedMotion = useReducedMotion()

  const flapVariants = {
    animate: prefersReducedMotion ? {} : {
      scaleY: [1, 0.45, 1],
      transition: {
        duration: 0.35,
        repeat: Infinity,
        repeatType: 'reverse' as const,
      },
    },
  }

  const driftVariants = {
    animate: prefersReducedMotion ? {} : {
      x: ['var(--x0)', 'var(--x1)', 'var(--x0)'],
      y: ['var(--y0)', 'var(--y1)', 'var(--y0)'],
      transition: {
        duration,
        repeat: Infinity,
        ease: 'easeInOut',
      },
    },
  }

  return (
    <motion.div
      className="absolute"
      style={{ width: size, animationDelay: `${delay}s` }}
      variants={driftVariants}
      animate="animate"
    >
      <motion.div
        variants={flapVariants}
        animate="animate"
        style={{ transformOrigin: '50% 60%' }}
        dangerouslySetInnerHTML={{ __html: BAT_SVG }}
      />
    </motion.div>
  )
}

export default function HalloweenDecor() {
  const { isHalloween } = useTheme()

  if (!isHalloween) return null

  const batConfigs = [
    { delay: 0, duration: 18, size: 56, x0: '62vw', y0: '90px', x1: '80vw', y1: '150px' },
    { delay: -6, duration: 23, size: 38, x0: '20vw', y0: '110px', x1: '36vw', y1: '70px' },
    { delay: -12, duration: 27, size: 30, x0: '88vw', y0: '420px', x1: '70vw', y1: '360px' },
    { delay: -3, duration: 21, size: 46, x0: '4vw', y0: '520px', x1: '14vw', y1: '460px' },
  ]

  return (
    <div className="fixed inset-0 pointer-events-none z-5" aria-hidden="true">
      {/* Top-left cobweb */}
      <div className="absolute top-16 left-0 w-56 h-56 opacity-28">
        <CobWeb />
      </div>

      {/* Bottom-right cobweb */}
      <div className="absolute bottom-0 right-0 w-56 h-56 opacity-28 rotate-180">
        <CobWeb />
      </div>

      {/* Bats */}
      {batConfigs.map((config, i) => (
        <div
          key={i}
          style={{
            '--x0': config.x0,
            '--y0': config.y0,
            '--x1': config.x1,
            '--y1': config.y1,
          } as React.CSSProperties}
        >
          <Bat
            delay={config.delay}
            duration={config.duration}
            size={config.size}
          />
        </div>
      ))}
    </div>
  )
}
