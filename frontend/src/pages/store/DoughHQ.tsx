import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Flame, Clock, AlertTriangle, CheckCircle, Timer, Loader2, X, Calendar, Check, Plus } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../../api/client'
import { Card, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'

interface StoreContext {
  storeId: number
  addedToScheduleItems: AddedToScheduleItem[]
  submitDoughScheduleItems: (items: {
    dough_type: string
    recommended_quantity?: number
    suggested_action?: string
    confidence?: number
  }[]) => Promise<void>
  clearDoughScheduleItems: () => Promise<void>
  appliedDoughTasks: any[]
  setAppliedDoughTasks: React.Dispatch<React.SetStateAction<any[]>>
}

interface AddedToScheduleItem {
  dough_type: string
  addedAt: string
}

// Add to Schedule Modal with selectable items
const AddToScheduleModal = ({
  isOpen,
  onClose,
  recommendations,
  addedItems,
  onSubmit
}: {
  isOpen: boolean
  onClose: () => void
  recommendations: any[]
  addedItems: AddedToScheduleItem[]
  onSubmit: (selectedTypes: string[]) => void
}) => {
  const [applied, setApplied] = useState(false)
  const [isApplying, setIsApplying] = useState(false)
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  const [submittedInfo, setSubmittedInfo] = useState<{ count: number; balls: number } | null>(null)

  const availableItems = recommendations?.filter(
    r => !addedItems.some(a => a.dough_type === r.dough_type)
  ) || []

  const toggleItem = (doughType: string) => {
    const newSelected = new Set(selectedItems)
    if (newSelected.has(doughType)) {
      newSelected.delete(doughType)
    } else {
      newSelected.add(doughType)
    }
    setSelectedItems(newSelected)
  }

  const selectAll = () => {
    setSelectedItems(new Set(availableItems.map(i => i.dough_type)))
  }

  const selectNone = () => {
    setSelectedItems(new Set())
  }

  const handleApply = async () => {
    if (selectedItems.size === 0) return
    const selectedRecs = availableItems.filter(r => selectedItems.has(r.dough_type))
    const totalBalls = selectedRecs.reduce((sum, r) => sum + r.recommended_quantity, 0)
    setSubmittedInfo({ count: selectedItems.size, balls: totalBalls })

    setIsApplying(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    onSubmit(Array.from(selectedItems))
    setIsApplying(false)
    setApplied(true)
  }

  const handleClose = () => {
    setApplied(false)
    setSubmittedInfo(null)
    setSelectedItems(new Set())
    onClose()
  }

  if (!isOpen) return null

  const selectedRecs = availableItems.filter(r => selectedItems.has(r.dough_type))
  const totalBalls = selectedRecs.reduce((sum, r) => sum + r.recommended_quantity, 0)

  const doughEmojis: Record<string, string> = {
    'Large Classic': '🍕',
    'Thin Crust': '🥐',
    'Deep Dish': '🍳',
    'Crazy Bread': '🧄',
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={handleClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="bg-surface rounded-2xl shadow-strong max-w-lg w-full max-h-[80vh] overflow-hidden"
          onClick={e => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-lc-orange/20 flex items-center justify-center">
                <Calendar className="w-5 h-5 text-lc-orange" />
              </div>
              <div>
                <h3 className="font-semibold text-text-primary">Add to Schedule</h3>
                <p className="text-sm text-text-secondary">Select items to add to dough prep schedule</p>
              </div>
            </div>
            <button onClick={handleClose} className="p-2 rounded-lg hover:bg-gray-100">
              <X className="w-5 h-5 text-text-secondary" />
            </button>
          </div>

          {/* Content */}
          <div className="p-5 max-h-96 overflow-y-auto">
            {applied && submittedInfo ? (
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="text-center py-8"
              >
                <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-8 h-8 text-green-600" />
                </div>
                <h4 className="text-lg font-semibold text-text-primary mb-2">Added to Schedule!</h4>
                <p className="text-text-secondary">
                  {submittedInfo.count} items ({submittedInfo.balls} dough balls) added to today's prep schedule.
                </p>
                <p className="text-sm text-text-tertiary mt-2">Team has been notified</p>
              </motion.div>
            ) : availableItems.length === 0 ? (
              <div className="text-center py-8">
                <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-gray-400" />
                </div>
                <h4 className="text-lg font-semibold text-text-primary mb-2">All Items Added</h4>
                <p className="text-text-secondary">All recommended items have been added to the schedule.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Selection controls */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">{selectedItems.size} of {availableItems.length} selected</span>
                  <div className="flex gap-2">
                    <button onClick={selectAll} className="text-xs text-lc-orange hover:underline">Select All</button>
                    <span className="text-text-tertiary">|</span>
                    <button onClick={selectNone} className="text-xs text-text-secondary hover:underline">Clear</button>
                  </div>
                </div>

                {availableItems.map((rec) => (
                  <div
                    key={rec.dough_type}
                    onClick={() => toggleItem(rec.dough_type)}
                    className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all ${
                      selectedItems.has(rec.dough_type)
                        ? 'bg-lc-orange/10 border-2 border-lc-orange/30'
                        : 'bg-surface-secondary border-2 border-transparent hover:border-gray-200'
                    }`}
                  >
                    <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-colors ${
                      selectedItems.has(rec.dough_type)
                        ? 'bg-lc-orange border-lc-orange'
                        : 'border-gray-300'
                    }`}>
                      {selectedItems.has(rec.dough_type) && (
                        <Check className="w-3 h-3 text-white" />
                      )}
                    </div>
                    <span className="text-2xl">{doughEmojis[rec.dough_type] || '🍞'}</span>
                    <div className="flex-1">
                      <p className="font-medium text-text-primary text-sm">{rec.dough_type}</p>
                      <p className="text-xs text-text-secondary">{rec.suggested_action}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-bold text-lc-orange">{rec.recommended_quantity}</p>
                      <p className="text-xs text-text-tertiary">balls</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-5 border-t border-gray-100 bg-surface-secondary">
            {!applied && availableItems.length > 0 ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-text-secondary">Total Balls</p>
                  <p className="text-xl font-bold text-text-primary">{totalBalls}</p>
                </div>
                <div className="flex gap-3">
                  <Button variant="secondary" onClick={handleClose}>Cancel</Button>
                  <Button onClick={handleApply} disabled={isApplying || selectedItems.size === 0}>
                    {isApplying ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Adding...
                      </>
                    ) : (
                      `Add to Schedule (${selectedItems.size})`
                    )}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex justify-end">
                <Button onClick={handleClose}>Done</Button>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// Loading component
const LoadingState = ({ message = "Retrieving data from Databricks..." }: { message?: string }) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="flex flex-col items-center justify-center py-8 gap-3"
  >
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    >
      <Loader2 className="w-8 h-8 text-lc-orange" />
    </motion.div>
    <div className="text-center">
      <p className="text-sm text-text-secondary">{message}</p>
      <motion.div
        className="flex items-center justify-center gap-1 mt-2"
        initial={{ opacity: 0.5 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-lc-orange" />
        <span className="w-1.5 h-1.5 rounded-full bg-lc-orange/60" />
        <span className="w-1.5 h-1.5 rounded-full bg-lc-orange/30" />
      </motion.div>
    </div>
  </motion.div>
)

// Inventory skeleton loader
const InventorySkeleton = () => (
  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
    {[1, 2, 3, 4].map((i) => (
      <motion.div
        key={i}
        className="p-4 bg-surface-secondary rounded-xl text-center"
        initial={{ opacity: 0.6 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
      >
        <div className="text-3xl mb-2 animate-pulse">🍕</div>
        <div className="h-4 w-20 mx-auto bg-gray-200 rounded animate-pulse mb-2" />
        <div className="h-8 w-12 mx-auto bg-gray-200 rounded animate-pulse mb-2" />
        <div className="h-3 w-16 mx-auto bg-gray-100 rounded animate-pulse" />
      </motion.div>
    ))}
    <div className="col-span-full text-center text-xs text-text-tertiary flex items-center justify-center gap-1">
      <Loader2 className="w-3 h-3 animate-spin" />
      <span>Loading from Databricks SQL Warehouse...</span>
    </div>
  </div>
)

const doughEmojis: Record<string, string> = {
  'Large Classic': '🍕',
  'Thin Crust': '🥐',
  'Deep Dish': '🍳',
  'Crazy Bread': '🧄',
}

export default function DoughHQ() {
  const {
    storeId,
    addedToScheduleItems,
    submitDoughScheduleItems,
    clearDoughScheduleItems,
    appliedDoughTasks: appliedTasks,
    setAppliedDoughTasks: setAppliedTasks
  } = useOutletContext<StoreContext>()
  const [showApplyModal, setShowApplyModal] = useState(false)
  const [isClearing, setIsClearing] = useState(false)

  const { data: inventory, isLoading: loadingInventory } = useQuery({
    queryKey: ['dough-inventory', storeId],
    queryFn: () => api.getDoughInventory(storeId),
  })

  const { data: schedule, isLoading: loadingSchedule } = useQuery({
    queryKey: ['dough-schedule', storeId],
    queryFn: () => api.getDoughSchedule(storeId),
  })

  const { data: recommendations, isLoading: loadingRecs } = useQuery({
    queryKey: ['dough-recommendations', storeId],
    queryFn: () => api.getDoughRecommendations(storeId),
  })

  const { data: alerts } = useQuery({
    queryKey: ['dough-alerts', storeId],
    queryFn: () => api.getDoughAlerts(storeId),
  })

  const { data: summary } = useQuery({
    queryKey: ['dough-summary', storeId],
    queryFn: () => api.getDoughSummary(storeId),
  })

  // Reconstruct appliedTasks from persisted state when recommendations load
  useEffect(() => {
    if (addedToScheduleItems.length > 0 && recommendations && appliedTasks.length === 0) {
      const baseId = (schedule?.tasks?.length || 0) + 2000
      const tasks = addedToScheduleItems
        .map((item, index) => {
          const rec = recommendations.find((r: any) => r.dough_type === item.dough_type)
          if (!rec) return null
          return {
            id: baseId + index,
            dough_type: rec.dough_type,
            quantity: rec.recommended_quantity,
            scheduled_time: rec.suggested_time,
            ready_time: rec.suggested_time,
            status: 'pending',
            priority: 'high',
            action: rec.suggested_action,
            isMLRecommendation: true,
          }
        })
        .filter(Boolean)
      if (tasks.length > 0) setAppliedTasks(tasks)
    }
  }, [addedToScheduleItems, recommendations, schedule])

  // Combine original schedule tasks with applied ML recommendation tasks, sorted by time
  const combinedSchedule = schedule ? {
    ...schedule,
    tasks: [
      ...(schedule.tasks || []),
      ...appliedTasks
    ].sort((a, b) => {
      const parseTime = (timeStr: string) => {
        const match = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/i)
        if (!match) return 0
        let hours = parseInt(match[1])
        const minutes = parseInt(match[2])
        const period = match[3].toUpperCase()
        if (period === 'PM' && hours !== 12) hours += 12
        if (period === 'AM' && hours === 12) hours = 0
        return hours * 60 + minutes
      }
      return parseTime(a.scheduled_time) - parseTime(b.scheduled_time)
    }),
    total_dough_balls: (schedule.total_dough_balls || 0) + appliedTasks.reduce((sum, t) => sum + t.quantity, 0)
  } : null

  const handleApplyRecommendations = async (selectedDoughTypes: string[]) => {
    const selectedRecs = recommendations?.filter(r => selectedDoughTypes.includes(r.dough_type)) || []

    const items = selectedRecs.map(rec => ({
      dough_type: rec.dough_type,
      recommended_quantity: rec.recommended_quantity,
      suggested_action: rec.suggested_action,
      confidence: rec.confidence,
    }))
    await submitDoughScheduleItems(items)

    const baseId = (schedule?.tasks?.length || 0) + appliedTasks.length + 2000
    const newTasks = selectedRecs.map((rec, index) => ({
      id: baseId + index,
      dough_type: rec.dough_type,
      quantity: rec.recommended_quantity,
      scheduled_time: rec.suggested_time,
      ready_time: rec.suggested_time,
      status: 'pending',
      priority: 'high',
      action: rec.suggested_action,
      isMLRecommendation: true,
    }))
    setAppliedTasks(prev => [...prev, ...newTasks])
  }

  const handleClearSchedule = async () => {
    setIsClearing(true)
    await clearDoughScheduleItems()
    setIsClearing(false)
  }

  const getStageColor = (stage: string) => ({
    'mixed': 'text-blue-600 bg-blue-50',
    'cold_hold': 'text-indigo-600 bg-indigo-50 dark:text-indigo-300 dark:bg-indigo-950',
    'tempering': 'text-amber-600 bg-amber-50',
    'ready': 'text-green-600 bg-green-50',
    'overproofed': 'text-red-600 bg-red-50',
  }[stage] || 'text-gray-600 bg-gray-50')

  const getStageIcon = (stage: string) => {
    if (stage === 'ready') return <CheckCircle className="w-4 h-4 text-green-500" />
    if (stage === 'tempering') return <Timer className="w-4 h-4 text-amber-500 animate-pulse" />
    return <Clock className="w-4 h-4 text-gray-400" />
  }

  return (
    <div className="space-y-6">
      {/* KPI Strip */}
      {summary && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-text-secondary">Dough Ready</p>
                <CheckCircle className="w-5 h-5 text-green-500" />
              </div>
              <p className="text-3xl font-bold text-text-primary">{summary.dough_ready_balls}</p>
              <p className="text-xs text-text-tertiary mt-1">balls ready</p>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-text-secondary">Rush Coverage</p>
                <Flame className="w-5 h-5 text-lc-orange" />
              </div>
              <p className="text-3xl font-bold text-lc-orange">{summary.rush_coverage_pct.toFixed(0)}%</p>
              <p className="text-xs text-text-tertiary mt-1">of peak demand</p>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-text-secondary">Projected Waste</p>
                <AlertTriangle className="w-5 h-5 text-red-500" />
              </div>
              <p className="text-3xl font-bold text-red-600">{summary.projected_waste_pct.toFixed(1)}%</p>
              <p className="text-xs text-text-tertiary mt-1">at risk</p>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-text-secondary">Forecast Need</p>
                <Timer className="w-5 h-5 text-amber-500" />
              </div>
              <p className="text-3xl font-bold text-text-primary">{summary.forecast_need_balls}</p>
              <p className="text-xs text-text-tertiary mt-1">balls needed</p>
            </div>
          </Card>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-text-primary">Dough HQ</h2>
          <p className="text-text-secondary">Dough prep and temper management</p>
        </div>
        {(combinedSchedule?.next_task || appliedTasks.find(t => t.status === 'pending')) && (
          <div className="flex items-center gap-3 px-4 py-2 bg-lc-orange/10 rounded-xl">
            <Timer className="w-5 h-5 text-lc-orange" />
            <div>
              <p className="text-sm font-medium text-text-primary">Next Task</p>
              <p className="text-xs text-text-secondary">
                {combinedSchedule?.next_task
                  ? `${combinedSchedule.next_task.dough_type} at ${combinedSchedule.next_task.scheduled_time}`
                  : appliedTasks.find(t => t.status === 'pending')
                    ? `${appliedTasks.find(t => t.status === 'pending')?.dough_type} at ${appliedTasks.find(t => t.status === 'pending')?.scheduled_time}`
                    : ''
                }
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Current Inventory */}
      <Card>
        <CardHeader
          title="Dough on Hand"
          subtitle="By type, stage, and age"
          icon={<Flame className="w-5 h-5" />}
        />
        <AnimatePresence mode="wait">
          {loadingInventory ? (
            <InventorySkeleton />
          ) : inventory?.length ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4"
            >
              {inventory.map((dough, index) => (
                <motion.div
                  key={dough.dough_type}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.05 }}
                  className="p-4 bg-surface-secondary rounded-xl"
                >
                  <div className="text-center mb-3">
                    <div className="text-3xl mb-2">{doughEmojis[dough.dough_type] || '🍞'}</div>
                    <h4 className="font-medium text-text-primary text-sm">{dough.dough_type}</h4>
                  </div>

                  <div className="space-y-3">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-lc-orange">{dough.quantity}</p>
                      <p className="text-xs text-text-tertiary">balls</p>
                    </div>

                    <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium w-full justify-center ${getStageColor(dough.stage)}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        dough.stage === 'ready' ? 'bg-green-500' :
                        dough.stage === 'tempering' ? 'bg-amber-500' :
                        dough.stage === 'cold_hold' ? 'bg-indigo-500' :
                        dough.stage === 'mixed' ? 'bg-blue-500' : 'bg-red-500'
                      }`} />
                      {dough.stage.replace('_', ' ').toUpperCase()}
                    </div>

                    {dough.age_days > 0 && (
                      <div className="text-center p-2 bg-surface rounded-lg border border-gray-100">
                        <p className="text-xs text-text-tertiary">Age</p>
                        <p className="text-sm font-semibold text-text-primary">{dough.age_days}d old</p>
                      </div>
                    )}

                    {dough.stage === 'tempering' && dough.temper_minutes_elapsed > 0 && (
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-lc-orange h-2 rounded-full"
                          style={{ width: `${Math.min(100, (dough.temper_minutes_elapsed / 180) * 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <div className="py-8 text-center text-text-tertiary">No dough inventory data</div>
          )}
        </AnimatePresence>
      </Card>

      {/* Main Grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Today's Prep and Temper Schedule */}
        <Card>
          <CardHeader
            title="Today's Prep and Temper Schedule"
            subtitle={`${combinedSchedule?.total_dough_balls || 0} total dough balls${appliedTasks.length > 0 ? ` (${appliedTasks.reduce((s, t) => s + t.quantity, 0)} from ML)` : ''}`}
            icon={<Clock className="w-5 h-5" />}
          />
          <AnimatePresence mode="wait">
            {loadingSchedule ? (
              <LoadingState message="Loading prep schedule from Databricks SQL Warehouse..." />
            ) : combinedSchedule?.tasks?.length ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-3 max-h-80 overflow-y-auto"
              >
                {combinedSchedule.tasks.map((task: any, index: number) => (
                  <motion.div
                    key={task.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.03 }}
                    className={`flex items-center gap-4 p-3 rounded-xl ${
                      task.status === 'in_progress' ? 'bg-amber-50 border border-amber-200' :
                      task.status === 'complete' ? 'bg-green-50' : 'bg-surface-secondary'
                    }`}
                  >
                    <div className="relative">
                      {getStageIcon(task.status)}
                      {task.isMLRecommendation && (
                        <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-lc-orange flex items-center justify-center border border-white">
                          <span className="text-white text-[6px] font-bold">ML</span>
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{doughEmojis[task.dough_type] || '🍞'}</span>
                        <span className="font-medium text-text-primary text-sm">{task.dough_type}</span>
                        {task.isMLRecommendation && (
                          <Badge variant="success" size="sm">ML Added</Badge>
                        )}
                      </div>
                      <p className="text-xs text-text-secondary">
                        {task.action} at {task.scheduled_time}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-lc-orange">{task.quantity}</p>
                      <p className="text-xs text-text-tertiary">balls</p>
                    </div>
                    <Badge
                      variant={task.priority === 'high' ? 'warning' : 'default'}
                      size="sm"
                    >
                      {task.priority}
                    </Badge>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">No dough tasks scheduled</div>
            )}
          </AnimatePresence>
        </Card>

        {/* ML Dough Recommendations */}
        <Card ml={true}>
          <CardHeader
            title="ML Dough Recommendations"
            subtitle="Based on demand forecast and rush timing"
            action={
              <div className="flex gap-2">
                {addedToScheduleItems.length > 0 && (
                  <Button size="sm" variant="secondary" onClick={handleClearSchedule} disabled={isClearing}>
                    {isClearing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                    Clear Schedule
                  </Button>
                )}
                <Button size="sm" onClick={() => setShowApplyModal(true)}><Plus className="w-4 h-4 mr-1" />Add to Schedule</Button>
              </div>
            }
          />

          <AddToScheduleModal
            isOpen={showApplyModal}
            onClose={() => setShowApplyModal(false)}
            recommendations={recommendations || []}
            addedItems={addedToScheduleItems}
            onSubmit={handleApplyRecommendations}
          />
          <AnimatePresence mode="wait">
            {loadingRecs ? (
              <LoadingState message="Generating dough recommendations from Databricks Model Serving..." />
            ) : recommendations?.length ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-3"
              >
                {recommendations.map((rec, index) => {
                  const addedItem = addedToScheduleItems.find(a => a.dough_type === rec.dough_type)
                  const isAdded = !!addedItem

                  return (
                    <motion.div
                      key={rec.dough_type}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.1 }}
                      className={`p-4 rounded-xl border relative overflow-hidden ${
                        isAdded
                          ? 'border-green-200'
                          : 'bg-gradient-to-r from-lc-orange/5 to-transparent border-lc-orange/10'
                      }`}
                    >
                      {isAdded && (
                        <div
                          className="absolute inset-0 bg-gradient-to-r from-green-100/70 via-emerald-50/60 to-teal-50/50 backdrop-blur-[2px]"
                          style={{ mixBlendMode: 'overlay' }}
                        />
                      )}

                      <div className="relative z-10">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{doughEmojis[rec.dough_type] || '🍞'}</span>
                            <span className="font-medium text-text-primary">{rec.dough_type}</span>
                            {isAdded && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200">
                                <CheckCircle className="w-3 h-3" />
                                Added to schedule
                              </span>
                            )}
                          </div>
                          <span className="text-2xl font-bold text-lc-orange">{rec.recommended_quantity}</span>
                        </div>
                        <p className="text-sm text-text-secondary">{rec.reason}</p>
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
                          {isAdded ? (
                            <span className="text-xs text-green-600 font-medium">
                              {addedItem.addedAt}
                            </span>
                          ) : (
                            <span className="text-xs text-text-tertiary">
                              Suggested: {rec.suggested_time}
                            </span>
                          )}
                          <Badge variant="success" size="sm">
                            {(rec.confidence * 100).toFixed(0)}% conf
                          </Badge>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">No recommendations available</div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      {/* Alerts */}
      {alerts && alerts.length > 0 && (
        <Card>
          <CardHeader
            title="Dough Alerts"
            icon={<AlertTriangle className="w-5 h-5" />}
          />
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {alerts.map((alert: any, index: number) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: index * 0.05 }}
                className={`p-4 rounded-xl ${
                  alert.severity === 'critical' ? 'bg-red-50 border border-red-200' :
                  alert.severity === 'warning' ? 'bg-amber-50 border border-amber-200' :
                  'bg-blue-50 border border-blue-200'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">{doughEmojis[alert.dough_type] || '🍞'}</span>
                  <span className="font-medium text-text-primary text-sm">{alert.dough_type}</span>
                  <Badge
                    variant={alert.severity === 'critical' ? 'error' : 'warning'}
                    size="sm"
                  >
                    {alert.type}
                  </Badge>
                </div>
                <p className="text-sm text-text-secondary mb-2">{alert.message}</p>
                <p className="text-xs text-lc-orange font-medium">{alert.action}</p>
              </motion.div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
