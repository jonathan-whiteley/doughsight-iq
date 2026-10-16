import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Map, BarChart3, Globe, ChevronLeft, Settings, MapPin, ChevronDown, Check, Filter, Home } from 'lucide-react'
import { BrandLockup } from '../components/BrandMark'
import ThemeSwitch from '../components/ThemeSwitch'
import { useState, useRef, useEffect } from 'react'

const navItems = [
  { path: 'map', label: 'Store Map', icon: Map, description: '3D store visualization' },
  { path: 'compare', label: 'Compare', icon: BarChart3, description: 'Rankings & AI insights' },
  { path: 'genie-one', label: 'Genie One', icon: Globe, description: 'Ask anything across Unity Catalog' },
]

// All 25 Metro Detroit stores
const ALL_STORES = [
  { id: 1, name: "Detroit Woodward Ave", city: "Detroit" },
  { id: 2, name: "Detroit Midtown", city: "Detroit" },
  { id: 3, name: "Dearborn Michigan Ave", city: "Dearborn" },
  { id: 4, name: "Royal Oak Main St", city: "Royal Oak" },
  { id: 5, name: "Troy Big Beaver", city: "Troy" },
  { id: 6, name: "Southfield", city: "Southfield" },
  { id: 7, name: "Livonia", city: "Livonia" },
  { id: 8, name: "Warren", city: "Warren" },
  { id: 9, name: "Sterling Heights", city: "Sterling Heights" },
  { id: 10, name: "Novi", city: "Novi" },
  { id: 11, name: "Ann Arbor State St", city: "Ann Arbor" },
  { id: 12, name: "Ypsilanti", city: "Ypsilanti" },
  { id: 13, name: "Canton", city: "Canton" },
  { id: 14, name: "Westland", city: "Westland" },
  { id: 15, name: "Farmington Hills", city: "Farmington Hills" },
  { id: 16, name: "Rochester Hills", city: "Rochester Hills" },
  { id: 17, name: "Pontiac", city: "Pontiac" },
  { id: 18, name: "Clinton Twp", city: "Clinton Twp" },
  { id: 19, name: "St Clair Shores", city: "St Clair Shores" },
  { id: 20, name: "Grosse Pointe", city: "Grosse Pointe" },
  { id: 21, name: "Taylor", city: "Taylor" },
  { id: 22, name: "Wyandotte", city: "Wyandotte" },
  { id: 23, name: "Hamtramck", city: "Hamtramck" },
  { id: 24, name: "Ferndale", city: "Ferndale" },
  { id: 25, name: "Auburn Hills", city: "Auburn Hills" },
]

export default function RegionalLayout() {
  const navigate = useNavigate()
  const [selectedStoreIds, setSelectedStoreIds] = useState<number[]>(ALL_STORES.map(s => s.id)) // All selected by default
  const [showStoreFilter, setShowStoreFilter] = useState(false)
  const [showSettingsMenu, setShowSettingsMenu] = useState(false)
  const filterRef = useRef<HTMLDivElement>(null)
  const settingsRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (filterRef.current && !filterRef.current.contains(event.target as Node)) {
        setShowStoreFilter(false)
      }
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
        setShowSettingsMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const toggleStore = (storeId: number) => {
    setSelectedStoreIds(prev => 
      prev.includes(storeId) 
        ? prev.filter(id => id !== storeId)
        : [...prev, storeId]
    )
  }

  const selectAll = () => setSelectedStoreIds(ALL_STORES.map(s => s.id))
  const deselectAll = () => setSelectedStoreIds([])

  return (
    <div className="min-h-screen bg-surface-secondary">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
          {/* Left: Back + Logo + Store Filter */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 -ml-2 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <ChevronLeft className="w-5 h-5 text-text-secondary" />
            </button>
            
            {/* Little Caesars Logo */}
            <BrandLockup />
            
            <div className="h-8 w-px bg-gray-200" />
            
            {/* Regional Info */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl yellow-gradient flex items-center justify-center">
                <MapPin className="w-4 h-4 text-gray-800" />
              </div>
              <div>
                <h1 className="font-medium text-text-primary text-sm">Regional Manager</h1>
                <p className="text-xs text-text-secondary">Metro Detroit</p>
              </div>
            </div>
            
            <div className="h-8 w-px bg-gray-200" />
            
            {/* Store Filter Dropdown */}
            <div className="relative" ref={filterRef}>
              <button
                onClick={() => setShowStoreFilter(!showStoreFilter)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-colors ${
                  selectedStoreIds.length < ALL_STORES.length 
                    ? 'bg-lc-orange/10 text-lc-orange' 
                    : 'hover:bg-gray-100 text-text-secondary'
                }`}
              >
                <Filter className="w-4 h-4" />
                <span className="text-sm font-medium">
                  {selectedStoreIds.length === ALL_STORES.length 
                    ? 'All 25 Stores' 
                    : `${selectedStoreIds.length} Stores`}
                </span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showStoreFilter ? 'rotate-180' : ''}`} />
              </button>
              
              {/* Multi-select Dropdown */}
              <AnimatePresence>
                {showStoreFilter && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="absolute top-full left-0 mt-2 w-80 bg-surface rounded-2xl shadow-strong border border-gray-100 py-2 z-50"
                  >
                    {/* Header with Select/Deselect All */}
                    <div className="px-4 py-2 border-b border-gray-100 flex items-center justify-between">
                      <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide">Filter Stores</p>
                      <div className="flex gap-2">
                        <button 
                          onClick={selectAll}
                          className="text-xs text-lc-orange hover:underline"
                        >
                          Select All
                        </button>
                        <span className="text-text-tertiary">|</span>
                        <button 
                          onClick={deselectAll}
                          className="text-xs text-red-500 hover:underline"
                        >
                          Clear All
                        </button>
                      </div>
                    </div>
                    
                    {/* Store List */}
                    <div className="max-h-64 overflow-y-auto py-1">
                      {ALL_STORES.map((store) => (
                        <button
                          key={store.id}
                          onClick={() => toggleStore(store.id)}
                          className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 transition-colors"
                        >
                          <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                            selectedStoreIds.includes(store.id)
                              ? 'bg-lc-orange border-lc-orange'
                              : 'border-gray-300'
                          }`}>
                            {selectedStoreIds.includes(store.id) && (
                              <Check className="w-3 h-3 text-white" />
                            )}
                          </div>
                          <div className="flex-1 text-left">
                            <p className="text-sm text-text-primary">{store.name}</p>
                          </div>
                          <span className="text-xs text-text-tertiary">{store.city}</span>
                        </button>
                      ))}
                    </div>
                    
                    {/* Footer */}
                    <div className="px-4 py-2 border-t border-gray-100 flex items-center justify-between">
                      <p className="text-xs text-text-secondary">
                        {selectedStoreIds.length} of {ALL_STORES.length} selected
                      </p>
                      <button
                        onClick={() => setShowStoreFilter(false)}
                        className="text-xs font-medium text-lc-orange hover:underline"
                      >
                        Done
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Center: Navigation */}
          <nav className="flex items-center bg-surface-secondary rounded-2xl p-1.5">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) => `
                  flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all
                  ${isActive 
                    ? 'bg-surface text-lc-orange shadow-soft' 
                    : 'text-text-secondary hover:text-text-primary'
                  }
                `}
              >
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>

          {/* Right: Settings */}
          <div className="relative" ref={settingsRef}>
            <button 
              onClick={() => setShowSettingsMenu(!showSettingsMenu)}
              className="p-2.5 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <motion.div
                animate={{ rotate: showSettingsMenu ? 180 : 0 }}
                transition={{ duration: 0.4, ease: "easeInOut" }}
              >
                <Settings className="w-5 h-5 text-text-secondary" />
              </motion.div>
            </button>
            
            {/* Settings Dropdown */}
            <AnimatePresence>
              {showSettingsMenu && (
                <motion.div
                  initial={{ opacity: 0, y: -10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.95 }}
                  transition={{ duration: 0.15 }}
                  className="absolute top-full right-0 mt-2 w-52 bg-surface rounded-xl shadow-strong border border-gray-100 py-1 z-50"
                >
                  <div className="px-3 py-2.5">
                    <ThemeSwitch />
                  </div>
                  <div className="h-px bg-gray-100 my-1" />
                  <button
                    onClick={() => {
                      setShowSettingsMenu(false)
                      navigate('/')
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors"
                  >
                    <Home className="w-4 h-4 text-text-secondary" />
                    <span className="text-sm font-medium text-text-primary">Home Page</span>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1600px] mx-auto px-6 py-6">
        {/* Persona Label */}
        <div className="mb-4 flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-lc-orange/20 rounded-full border border-lc-orange/30">
            <MapPin className="w-4 h-4 text-lc-orange-dark" />
            <span className="text-sm font-medium text-lc-orange-dark">Regional Manager View</span>
          </div>
        </div>
        
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <Outlet context={{ selectedStoreIds, allStores: ALL_STORES }} />
        </motion.div>
      </main>
    </div>
  )
}


