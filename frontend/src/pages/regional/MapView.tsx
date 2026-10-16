import React, { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { useOutletContext } from 'react-router-dom'
import Map, { NavigationControl } from 'react-map-gl/maplibre'
import { ScatterplotLayer } from '@deck.gl/layers'
import { DeckGL } from '@deck.gl/react'
import { MapPin, X, TrendingUp, TrendingDown, DollarSign, Star, Loader2, ChevronDown, ChevronUp, BarChart3, Percent } from 'lucide-react'
import { useTheme } from '../../theme/ThemeContext'
import { api } from '../../api/client'
import { Card, StatCard } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'

interface RegionalContext {
  selectedStoreIds: number[]
  allStores: { id: number; name: string; city: string }[]
}

// Loading component
const LoadingOverlay = ({ message = "Retrieving data from Databricks..." }: { message?: string }) => (
  <motion.div 
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="absolute inset-0 bg-surface/80 backdrop-blur-sm flex flex-col items-center justify-center z-10 rounded-2xl"
  >
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    >
      <Loader2 className="w-10 h-10 text-lc-orange" />
    </motion.div>
    <div className="text-center mt-4">
      <p className="text-text-primary font-medium">{message}</p>
      <motion.div 
        className="flex items-center justify-center gap-1.5 mt-3"
        initial={{ opacity: 0.5 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
      >
        <span className="w-2 h-2 rounded-full bg-lc-orange" />
        <span className="w-2 h-2 rounded-full bg-lc-orange/60" />
        <span className="w-2 h-2 rounded-full bg-lc-orange/30" />
      </motion.div>
    </div>
  </motion.div>
)

// Metro Detroit center coordinates
const INITIAL_VIEW_STATE = {
  longitude: -83.20,
  latitude: 42.45,
  zoom: 9.3,
  pitch: 45,
  bearing: 0,
}

interface StoreLocation {
  store_id: number
  name: string
  address: string
  city: string
  latitude: number
  longitude: number
  sales_today?: number
  rank?: number
  trend?: string
}

export default function MapView() {
  const { selectedStoreIds } = useOutletContext<RegionalContext>()
  const theme = useTheme()
  const [selectedStore, setSelectedStore] = useState<StoreLocation | null>(null)
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE)
  const [expandedDetails, setExpandedDetails] = useState(false)
  const [expandedTableRow, setExpandedTableRow] = useState<number | null>(null)

  const { data: locations, isLoading: loadingLocations } = useQuery({
    queryKey: ['store-locations'],
    queryFn: () => api.getStoreLocations(),
  })

  const { data: storesData, isLoading: loadingStores } = useQuery({
    queryKey: ['stores'],
    queryFn: () => api.getStores(),
  })

  // Fetch detailed store data when a store is selected and expanded
  const { data: storeDetail, isLoading: loadingDetail } = useQuery({
    queryKey: ['store-detail', selectedStore?.store_id],
    queryFn: () => selectedStore ? api.getStoreDetail(selectedStore.store_id) : null,
    enabled: !!selectedStore && expandedDetails,
  })

  const isLoading = loadingLocations || loadingStores

  // Reset expanded state when store changes
  useEffect(() => {
    setExpandedDetails(false)
  }, [selectedStore?.store_id])

  // Merge location and KPI data, filter by selected store IDs
  const stores = useMemo(() => {
    if (!locations || !storesData?.stores) return []
    
    return locations
      .filter((loc: StoreLocation) => selectedStoreIds.includes(loc.store_id))
      .map((loc: StoreLocation) => {
        const kpi = storesData.stores.find((s: any) => s.store_id === loc.store_id)
        return {
          ...loc,
          sales_today: kpi?.sales_today || 0,
          sales_wtd: kpi?.sales_wtd || 0,
          sales_mtd: kpi?.sales_mtd || 0,
          labor_cost_pct: kpi?.labor_cost_pct || 0,
          rank: kpi?.rank || 0,
          trend: kpi?.trend || 'flat',
          vs_forecast_pct: kpi?.vs_forecast_pct || 0,
        }
      })
  }, [locations, storesData, selectedStoreIds])

  // Update layers when stores change
  const layerKey = useMemo(() => selectedStoreIds.join('-'), [selectedStoreIds])

  // Create Deck.gl layer for 3D visualization - update when stores change
  const layers = useMemo(() => [
    new ScatterplotLayer({
      id: `stores-layer-${layerKey}`,
      data: stores,
      pickable: true,
      opacity: 0.9,
      stroked: true,
      filled: true,
      radiusScale: 1,
      radiusMinPixels: 20,
      radiusMaxPixels: 40,
      lineWidthMinPixels: 2,
      getPosition: (d: any) => [d.longitude, d.latitude],
      getRadius: (d: any) => Math.max(200, (d.sales_today || 2000) / 10),
      getFillColor: (d: any) => {
        if (d.trend === 'up') return [...theme.map.trendUp, 210]
        if (d.trend === 'down') return [...theme.map.trendDown, 200]
        return theme.isHalloween ? [181, 123, 255, 200] : [26, 26, 26, 190] // purple / LC black (flat)
      },
      getLineColor: theme.isHalloween ? [232, 220, 200, 255] : [255, 255, 255, 255],
      onClick: (info: any) => {
        if (info.object) {
          setSelectedStore(info.object)
          setExpandedDetails(false)
        }
      },
      updateTriggers: {
        getPosition: layerKey,
        getRadius: layerKey,
        getFillColor: layerKey,
      },
    }),
  ], [stores, layerKey])

  const formatCurrency = (value: number) => 
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-text-primary">Store Map</h2>
          <p className="text-text-secondary">Interactive 3D view of all locations</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: `rgb(${theme.map.trendUp.join(',')})` }} />
            <span className="text-text-secondary">Trending Up</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: theme.isHalloween ? '#120D18' : '#1A1A1A' }} />
            <span className="text-text-secondary">Stable</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: `rgb(${theme.map.trendDown.join(',')})` }} />
            <span className="text-text-secondary">Trending Down</span>
          </div>
        </div>
      </div>

      {/* Map Container */}
      <div className="relative h-[600px] rounded-2xl overflow-hidden shadow-medium">
        {/* Loading Overlay */}
        <AnimatePresence>
          {isLoading && (
            <LoadingOverlay message="Loading store data from Databricks Unity Catalog..." />
          )}
        </AnimatePresence>

        <DeckGL
          viewState={viewState}
          onViewStateChange={({ viewState }: any) => setViewState(viewState)}
          controller={true}
          layers={layers}
          style={{ width: '100%', height: '100%' }}
        >
          <Map
            mapStyle={theme.map.basemap}
            style={{ width: '100%', height: '100%' }}
          >
            <NavigationControl position="top-right" />
          </Map>
        </DeckGL>

        {/* Store Markers (fallback for non-Deck.gl interaction) */}
        {stores.map((store: any) => (
          <motion.div
            key={store.store_id}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute"
            style={{
              // This is a simplified positioning; actual positioning is handled by Deck.gl
              display: 'none', // Hidden since we use Deck.gl layer
            }}
          >
            <MapPin className="w-8 h-8 text-lc-orange" />
          </motion.div>
        ))}

        {/* Selected Store Panel */}
        <AnimatePresence>
          {selectedStore && (
            <motion.div
              initial={{ x: 100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 100, opacity: 0 }}
              className="absolute top-4 right-4 w-80 bg-surface/95 backdrop-blur-md rounded-2xl shadow-strong p-5 max-h-[90%] overflow-y-auto"
            >
              <button
                onClick={() => setSelectedStore(null)}
                className="absolute top-3 right-3 p-1.5 rounded-lg hover:bg-gray-100 z-10"
              >
                <X className="w-4 h-4 text-text-secondary" />
              </button>

              <div className="mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={selectedStore.trend === 'up' ? 'success' : selectedStore.trend === 'down' ? 'error' : 'default'}>
                    #{selectedStore.rank || '?'}
                  </Badge>
                  <span className="text-sm text-text-secondary">
                    {selectedStore.trend === 'up' ? <TrendingUp className="w-4 h-4 text-green-500" /> :
                     selectedStore.trend === 'down' ? <TrendingDown className="w-4 h-4 text-red-500" /> : null}
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-text-primary">{selectedStore.name}</h3>
                <p className="text-sm text-text-secondary">{selectedStore.address}, {selectedStore.city}</p>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-surface-secondary rounded-xl p-3">
                  <p className="text-xs text-text-secondary mb-1">Sales Today</p>
                  <p className="text-lg font-semibold text-lc-orange">
                    {formatCurrency(selectedStore.sales_today || 0)}
                  </p>
                </div>
                <div className="bg-surface-secondary rounded-xl p-3">
                  <p className="text-xs text-text-secondary mb-1">vs Forecast</p>
                  <p className={`text-lg font-semibold ${
                    (selectedStore as any).vs_forecast_pct >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {(selectedStore as any).vs_forecast_pct >= 0 ? '+' : ''}{((selectedStore as any).vs_forecast_pct || 0).toFixed(1)}%
                  </p>
                </div>
              </div>

              {/* Expandable Store Details Button */}
              <button 
                onClick={() => setExpandedDetails(!expandedDetails)}
                className="w-full py-2.5 bg-lc-orange text-white rounded-xl font-medium hover:bg-lc-orange-dark transition-colors flex items-center justify-center gap-2"
              >
                View Store Details
                {expandedDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {/* Expanded Store Details */}
              <AnimatePresence>
                {expandedDetails && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      {loadingDetail ? (
                        <div className="flex flex-col items-center justify-center py-6">
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                          >
                            <Loader2 className="w-6 h-6 text-lc-orange" />
                          </motion.div>
                          <p className="text-xs text-text-secondary mt-2">Loading from Databricks SQL Warehouse...</p>
                        </div>
                      ) : storeDetail ? (
                        <div className="space-y-4">
                          {/* Store Info */}
                          <div>
                            <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">Store Info</h4>
                            <div className="space-y-2 text-sm">
                              <div className="flex justify-between">
                                <span className="text-text-secondary">Manager</span>
                                <span className="text-text-primary font-medium">{storeDetail.manager_name}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-text-secondary">Phone</span>
                                <span className="text-text-primary">{storeDetail.phone}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-text-secondary">Square Feet</span>
                                <span className="text-text-primary">{storeDetail.sqft?.toLocaleString()} sqft</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-text-secondary">Staff Count</span>
                                <span className="text-text-primary">{storeDetail.staff_count} employees</span>
                              </div>
                            </div>
                          </div>

                          {/* KPI Section */}
                          <div>
                            <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">Performance</h4>
                            <div className="grid grid-cols-2 gap-2">
                              <div className="bg-green-50 rounded-lg p-3">
                                <div className="flex items-center gap-1 text-green-600 mb-1">
                                  <DollarSign className="w-3 h-3" />
                                  <span className="text-xs font-medium">Sales WTD</span>
                                </div>
                                <p className="text-lg font-bold text-green-700">
                                  {formatCurrency((selectedStore as any).sales_wtd || 0)}
                                </p>
                              </div>
                              <div className="bg-blue-50 rounded-lg p-3">
                                <div className="flex items-center gap-1 text-blue-600 mb-1">
                                  <BarChart3 className="w-3 h-3" />
                                  <span className="text-xs font-medium">Sales MTD</span>
                                </div>
                                <p className="text-lg font-bold text-blue-700">
                                  {formatCurrency((selectedStore as any).sales_mtd || 0)}
                                </p>
                              </div>
                              <div className="bg-amber-50 rounded-lg p-3">
                                <div className="flex items-center gap-1 text-amber-600 mb-1">
                                  <Percent className="w-3 h-3" />
                                  <span className="text-xs font-medium">Labor Cost</span>
                                </div>
                                <p className="text-lg font-bold text-amber-700">
                                  {((selectedStore as any).labor_cost_pct || 0).toFixed(1)}%
                                </p>
                              </div>
                              <div className="bg-purple-50 rounded-lg p-3">
                                <div className="flex items-center gap-1 text-purple-600 mb-1">
                                  <DollarSign className="w-3 h-3" />
                                  <span className="text-xs font-medium">Sales YTD</span>
                                </div>
                                <p className="text-lg font-bold text-purple-700">
                                  {formatCurrency(storeDetail.sales_ytd || 0)}
                                </p>
                              </div>
                            </div>
                          </div>

                          {/* Store Ranking */}
                          <div className="bg-surface-secondary rounded-lg p-3">
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-text-secondary">Regional Ranking</span>
                              <div className="flex items-center gap-2">
                                <Badge variant={storeDetail.rank <= 5 ? 'success' : storeDetail.rank >= 20 ? 'error' : 'default'}>
                                  #{storeDetail.rank} of 25
                                </Badge>
                                {(selectedStore as any).vs_forecast_pct >= 0 ? (
                                  <TrendingUp className="w-4 h-4 text-green-500" />
                                ) : (
                                  <TrendingDown className="w-4 h-4 text-red-500" />
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-text-secondary text-center py-4">
                          Unable to load store details
                        </p>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Stores"
          value={stores.length}
          icon={<MapPin className="w-5 h-5" />}
        />
        <StatCard
          label="District Sales Today"
          value={formatCurrency(stores.reduce((sum: number, s: any) => sum + (s.sales_today || 0), 0))}
          icon={<DollarSign className="w-5 h-5" />}
        />
        <StatCard
          label="Stores Trending Up"
          value={stores.filter((s: any) => s.trend === 'up').length}
          icon={<TrendingUp className="w-5 h-5" />}
          trend="up"
        />
        <StatCard
          label="Top Performer"
          value={(() => {
            // Find the best ranked store from the currently selected stores
            const sortedByRank = [...stores].sort((a: any, b: any) => (a.rank || 999) - (b.rank || 999))
            return sortedByRank[0]?.name || '-'
          })()}
          icon={<Star className="w-5 h-5" />}
        />
      </div>

      {/* Store Rankings Table */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-text-primary">Store Rankings</h3>
          <Badge variant="info">{stores.length} stores</Badge>
        </div>
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center py-12 gap-3"
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              >
                <Loader2 className="w-8 h-8 text-lc-orange" />
              </motion.div>
              <p className="text-sm text-text-secondary">Loading store rankings from Databricks SQL Warehouse...</p>
            </motion.div>
          ) : (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="overflow-x-auto"
            >
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-text-secondary border-b border-gray-100">
                    <th className="pb-3 font-medium w-8"></th>
                    <th className="pb-3 font-medium">Rank</th>
                    <th className="pb-3 font-medium">Store</th>
                    <th className="pb-3 font-medium">City</th>
                    <th className="pb-3 font-medium text-right">Sales Today</th>
                    <th className="pb-3 font-medium text-right">vs Forecast</th>
                    <th className="pb-3 font-medium text-right">Trend</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {[...stores].sort((a: any, b: any) => (a.rank || 999) - (b.rank || 999)).map((store: any, index: number) => (
                    <React.Fragment key={store.store_id}>
                      <motion.tr
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.03 }}
                        className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer ${
                          expandedTableRow === store.store_id ? 'bg-gray-50' : ''
                        }`}
                        onClick={() => setExpandedTableRow(expandedTableRow === store.store_id ? null : store.store_id)}
                      >
                        <td className="py-3 pl-2">
                          {expandedTableRow === store.store_id ? (
                            <ChevronUp className="w-4 h-4 text-text-secondary" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-text-tertiary" />
                          )}
                        </td>
                        <td className="py-3">
                          <Badge variant={store.rank <= 3 ? 'success' : store.rank >= 20 ? 'error' : 'default'}>
                            #{store.rank || index + 1}
                          </Badge>
                        </td>
                        <td className="py-3 font-medium text-text-primary">{store.name}</td>
                        <td className="py-3 text-text-secondary">{store.city}</td>
                        <td className="py-3 text-right font-medium tabular-nums">{formatCurrency(store.sales_today || 0)}</td>
                        <td className="py-3 text-right">
                          <span className={`font-medium tabular-nums px-2 py-0.5 rounded ${
                            (store.vs_forecast_pct || 0) >= 5 ? 'bg-green-100 text-green-700' :
                            (store.vs_forecast_pct || 0) >= 0 ? 'bg-green-50 text-green-600' :
                            (store.vs_forecast_pct || 0) >= -5 ? 'bg-amber-50 text-amber-600' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {(store.vs_forecast_pct || 0) >= 0 ? '+' : ''}{(store.vs_forecast_pct || 0).toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3 text-right">
                          {store.trend === 'up' ? (
                            <TrendingUp className="w-4 h-4 text-green-500 inline" />
                          ) : store.trend === 'down' ? (
                            <TrendingDown className="w-4 h-4 text-red-500 inline" />
                          ) : (
                            <span className="text-text-tertiary">-</span>
                          )}
                        </td>
                      </motion.tr>
                      
                      {/* Expanded Row Details */}
                      <AnimatePresence>
                        {expandedTableRow === store.store_id && (
                          <motion.tr
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                          >
                            <td colSpan={7} className="px-4 py-4 bg-gray-50 border-b border-gray-100">
                              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                                <div className="bg-surface rounded-lg p-3">
                                  <p className="text-xs text-text-secondary mb-1">Sales WTD</p>
                                  <p className="text-lg font-bold text-green-600">
                                    {formatCurrency(store.sales_wtd || 0)}
                                  </p>
                                </div>
                                <div className="bg-surface rounded-lg p-3">
                                  <p className="text-xs text-text-secondary mb-1">Sales MTD</p>
                                  <p className="text-lg font-bold text-blue-600">
                                    {formatCurrency(store.sales_mtd || 0)}
                                  </p>
                                </div>
                                <div className="bg-surface rounded-lg p-3">
                                  <p className="text-xs text-text-secondary mb-1">Labor Cost %</p>
                                  <p className={`text-lg font-bold ${
                                    (store.labor_cost_pct || 0) <= 25 ? 'text-green-600' :
                                    (store.labor_cost_pct || 0) <= 30 ? 'text-amber-600' :
                                    'text-red-600'
                                  }`}>
                                    {(store.labor_cost_pct || 0).toFixed(1)}%
                                  </p>
                                </div>
                                <div className="bg-surface rounded-lg p-3">
                                  <p className="text-xs text-text-secondary mb-1">Regional Rank</p>
                                  <p className="text-lg font-bold text-text-primary">
                                    #{store.rank || '?'} <span className="text-xs font-normal text-text-secondary">of 25</span>
                                  </p>
                                </div>
                                <div className="bg-surface rounded-lg p-3">
                                  <p className="text-xs text-text-secondary mb-1">vs Forecast</p>
                                  <p className={`text-lg font-bold ${
                                    (store.vs_forecast_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                                  }`}>
                                    {(store.vs_forecast_pct || 0) >= 0 ? '+' : ''}{(store.vs_forecast_pct || 0).toFixed(1)}%
                                  </p>
                                </div>
                                <div className="bg-surface rounded-lg p-3 flex items-center justify-center">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      setSelectedStore(store)
                                      // Scroll to top to show the map
                                      window.scrollTo({ top: 0, behavior: 'smooth' })
                                    }}
                                    className="text-sm font-medium text-lc-orange hover:text-lc-orange-dark flex items-center gap-1"
                                  >
                                    View on Map
                                    <MapPin className="w-4 h-4" />
                                  </button>
                                </div>
                              </div>
                            </td>
                          </motion.tr>
                        )}
                      </AnimatePresence>
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </div>
  )
}


