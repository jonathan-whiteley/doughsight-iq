import React, { createContext, useContext, useEffect, useState } from 'react'
import { MASCOT } from '../brand'

interface ThemeContextType {
  isHalloween: boolean
  toggle: () => void
  chart: {
    orange: string
    purple: string
    green: string
    cream: string
    orange_alt: string
    gridColor: string
    tickColor: string
  }
  map: {
    basemap: string
    trendUp: [number, number, number]
    trendDown: [number, number, number]
    outline: string
  }
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const STORAGE_KEY = 'doughsight-theme'

/** ?theme=halloween|light wins (handy for demo links), then the saved choice. */
function initialHalloween(): boolean {
  const param = new URLSearchParams(window.location.search).get('theme')
  if (param === 'halloween' || param === 'light') {
    localStorage.setItem(STORAGE_KEY, param)
    return param === 'halloween'
  }
  return localStorage.getItem(STORAGE_KEY) === 'halloween'
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [isHalloween, setIsHalloween] = useState(initialHalloween)

  useEffect(() => {
    document.documentElement.classList.toggle('halloween', isHalloween)
    document.documentElement.classList.toggle('dark', isHalloween)
    localStorage.setItem(STORAGE_KEY, isHalloween ? 'halloween' : 'light')
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    if (icon) {
      icon.type = isHalloween ? 'image/png' : 'image/svg+xml'
      icon.href = isHalloween ? MASCOT.halloween : MASCOT.default
    }
  }, [isHalloween])

  const toggle = () => setIsHalloween(v => !v)

  const chartTheme = isHalloween
    ? {
        orange: '#FF6000',
        purple: '#B57BFF',
        green: '#7CE38B',
        cream: '#E8DCC8',
        orange_alt: '#FF9A4D',
        gridColor: '#2E2538',
        tickColor: '#857C93',
      }
    : {
        orange: '#FF6000',
        purple: '#1A1A1A',
        green: '#16A34A',
        cream: '#FFFFFF',
        orange_alt: '#FF8844',
        gridColor: '#F0F0F0',
        tickColor: '#9CA3AF',
      }

  const mapTheme = isHalloween
    ? {
        basemap: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
        trendUp: [255, 96, 0] as [number, number, number],
        trendDown: [248, 113, 113] as [number, number, number],
        outline: '#120D18',
      }
    : {
        basemap: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
        trendUp: [255, 96, 0] as [number, number, number],
        trendDown: [239, 68, 68] as [number, number, number],
        outline: '#FFFFFF',
      }

  return (
    <ThemeContext.Provider
      value={{
        isHalloween,
        toggle,
        chart: chartTheme,
        map: mapTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
