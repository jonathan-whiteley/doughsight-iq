import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Store, MapPin, ChevronRight } from 'lucide-react'
import { PRODUCT_NAME, TAGLINE } from '../brand'
import { useTheme } from '../theme/ThemeContext'
import BrandMark, { BrandLockup } from '../components/BrandMark'
import ThemeSwitch from '../components/ThemeSwitch'

const personas = [
  {
    id: 'store',
    title: 'Store Manager',
    description: 'Real-time operations, forecasting, labor, inventory, and dough HQ for your store',
    icon: Store,
    path: '/store/operations',
    color: 'lc-orange',
    features: ['Live Sales Dashboard', 'Demand Forecasting', 'Labor Optimization', 'Inventory Tracking', 'Dough HQ Schedule'],
  },
  {
    id: 'regional',
    title: 'Franchise Manager',
    description: 'Multi-store overview, performance comparison, and AI-powered insights across metro Detroit',
    icon: MapPin,
    path: '/regional/map',
    color: 'lc-orange',
    features: ['Store Map View', 'Performance Rankings', 'AI Analytics Chat', 'Regional KPIs'],
  },
]

export default function Login() {
  const navigate = useNavigate()
  const { isHalloween } = useTheme()

  return (
    <div className={`min-h-screen flex items-center justify-center p-8 transition-colors duration-300 ${isHalloween ? 'bg-gradient-to-br from-[#120D18] via-[#1E1726] to-[#2A2033]' : 'bg-gradient-to-br from-white via-surface-secondary to-lc-cream'}`}>
      {/* Background Pattern */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-1/2 -right-1/2 w-full h-full">
          <div className="w-[800px] h-[800px] rounded-full bg-gradient-to-br from-lc-orange/5 to-transparent blur-3xl" />
        </div>
        <div className="absolute -bottom-1/2 -left-1/2 w-full h-full">
          <div className="w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-lc-orange-light/5 to-transparent blur-3xl" />
        </div>
      </div>

      {/* Theme slider: Light / Spooky */}
      <div className="fixed top-6 right-6 z-40">
        <ThemeSwitch />
      </div>

      <div className="relative z-10 max-w-5xl w-full">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          {/* Little Caesars Logo */}
          <div className="flex justify-center mb-8">
            {isHalloween
              ? <BrandLockup height="h-14" countHeight="h-40" />
              : <img src="/lc-logo.svg" alt="Little Caesars" className="h-14" />}
          </div>

          <div className="flex items-center justify-center gap-3 mb-6">
            {!isHalloween && <BrandMark className="h-16 w-auto object-contain" />}
            <h1 className="text-4xl font-bold">
              <span className="gradient-text">{PRODUCT_NAME.split(' ')[0]}</span>
              <span className="text-text-primary"> {PRODUCT_NAME.split(' ').slice(1).join(' ')}</span>
            </h1>
          </div>
          <p className="text-xl text-text-secondary max-w-xl mx-auto">
            {TAGLINE}
          </p>
        </motion.div>

        {/* Persona Cards */}
        <div className="grid md:grid-cols-2 gap-6">
          {personas.map((persona, index) => (
            <motion.button
              key={persona.id}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 + index * 0.1 }}
              onClick={() => navigate(persona.path)}
              className="group relative bg-surface rounded-3xl p-8 shadow-soft hover:shadow-strong transition-all duration-300 text-left border border-gray-100 hover:border-transparent overflow-hidden"
            >
              {/* Hover gradient overlay */}
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-br from-lc-orange/5 to-transparent" />

              <div className="relative z-10">
                {/* Icon */}
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-6 bg-lc-orange/10 text-lc-orange">
                  <persona.icon className="w-7 h-7" />
                </div>

                {/* Title & Description */}
                <h2 className="text-2xl font-semibold text-text-primary mb-2 group-hover:text-lc-orange transition-colors">
                  {persona.title}
                </h2>
                <p className="text-text-secondary mb-6">
                  {persona.description}
                </p>

                {/* Features */}
                <ul className="space-y-2 mb-6">
                  {persona.features.map((feature, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-text-secondary">
                      <div className="w-1.5 h-1.5 rounded-full bg-lc-orange" />
                      {feature}
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                <div className="flex items-center gap-2 text-lc-orange font-medium group-hover:gap-3 transition-all">
                  <span>Continue as {persona.title}</span>
                  <ChevronRight className="w-5 h-5" />
                </div>
              </div>
            </motion.button>
          ))}
        </div>

        {/* Footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-center mt-12 text-sm text-text-tertiary"
        >
          <p>Powered by Databricks • Unity Catalog • Mosaic AI • AI/BI Genie • Lakebase</p>
        </motion.div>
      </div>
    </div>
  )
}


