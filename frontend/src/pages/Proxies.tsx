import { useEffect, useState, useMemo } from 'react'
import {
    RefreshCw,
    Activity,
    Zap,
    Signal,
    SignalHigh,
    SignalMedium,
    SignalLow,
    ArrowUpDown,
    Network,
    Loader2
} from 'lucide-react'
import { toast } from 'sonner'
import { proxiesApi, ProxyNode } from '../services/api'
import { cn } from "@/lib/utils"
import { useLanguage } from '@/contexts/LanguageContext'
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"

// Module-level caches to prevent UI clear flickering during navigations
let cachedProxies: ProxyNode[] = []
let cachedPoolStatus = { total: 0, active: 0, idle: 0 }
let cachedClashStatus = { connected: false, current_node: null as string | null }

// 动态国家名称映射（用于筛选器显示，按需扩展）
const getRegionDisplay = (code: string): { flag: string; label: string } => ({
    flag: `https://flagcdn.com/w40/${code.toLowerCase()}.png`,
    label: code,
})


export default function Proxies() {
    const [nodes, setNodes] = useState<ProxyNode[]>(cachedProxies)
    const [poolStatus, setPoolStatus] = useState(cachedPoolStatus)
    const [clashStatus, setClashStatus] = useState(cachedClashStatus)
    const [syncing, setSyncing] = useState(false)
    const [testing, setTesting] = useState(false)
    const [restarting, setRestarting] = useState(false)
    const [nodeOperations, setNodeOperations] = useState<Record<number, 'testing' | 'toggling'>>({})
    const { t } = useLanguage()

    const [filters, setFilters] = useState({ type: 'all', region: 'all', enabled: 'all' })
    const [bulkMode, setBulkMode] = useState(false)
    const [selectedIds, setSelectedIds] = useState<Record<number, boolean>>({})
    const [bulkApplying, setBulkApplying] = useState(false)
    const [sortBy, setSortBy] = useState<'usage' | 'latency' | 'name'>('name')
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

    useEffect(() => {
        fetchData()
    }, [])

    const fetchData = async () => {
        try {
            const [proxiesData, poolData, clashData] = await Promise.all([
                proxiesApi.list(),
                proxiesApi.getPoolStatus(),
                proxiesApi.getClashStatus()
            ])
            cachedProxies = proxiesData
            cachedPoolStatus = poolData
            cachedClashStatus = clashData
            setNodes(proxiesData)
            setPoolStatus(poolData)
            setClashStatus(clashData)
        } catch (error) {
            console.error('Failed to fetch data:', error)
        }
    }

    const handleSync = async () => {
        setSyncing(true)
        try {
            await proxiesApi.sync()
            toast.success('Nodes synchronized successfully')
            await fetchData()
        } catch (error: any) {
            toast.error(error.message || 'Synchronization failed')
        } finally {
            setSyncing(false)
        }
    }

    const handleTestAll = async () => {
        setTesting(true)
        try {
            await proxiesApi.testLatency()
            toast.success('Latency test completed')
            await fetchData()
        } catch (error: any) {
            toast.error(error.message || 'Latency test failed')
        } finally {
            setTesting(false)
        }
    }

    const handleToggle = async (id: number) => {
        setNodeOperations(prev => ({ ...prev, [id]: 'toggling' }))
        try {
            await proxiesApi.toggle(id)
            toast.success('Node status updated')
            await fetchData()
        } catch (error: any) {
            toast.error(error.message || 'Update failed')
        } finally {
            setNodeOperations(prev => {
                const next = { ...prev }
                delete next[id]
                return next
            })
        }
    }

    const selectedCount = useMemo(
        () => Object.values(selectedIds).filter(Boolean).length,
        [selectedIds]
    )

    const toggleSelection = (id: number) => {
        setSelectedIds(prev => ({ ...prev, [id]: !prev[id] }))
    }

    const clearSelection = () => {
        setSelectedIds({})
    }

    const handleSelectAllVisible = () => {
        const next: Record<number, boolean> = {}
        filteredNodes.forEach(n => {
            if (filters.enabled === 'all' || n.is_enabled === (filters.enabled === 'true')) {
                next[n.id] = true
            }
        })
        setSelectedIds(next)
    }

    const handleBulkToggle = async (isEnabled: boolean) => {
        const ids = Object.keys(selectedIds)
            .filter(id => selectedIds[Number(id)])
            .map(id => Number(id))
        if (ids.length === 0) {
            toast.error('Please select at least one node')
            return
        }
        setBulkApplying(true)
        try {
            await proxiesApi.batchToggle(ids, isEnabled)
            toast.success(`Updated ${ids.length} nodes`)
            await fetchData()
            clearSelection()
        } catch (error: any) {
            toast.error(error.message || 'Batch update failed')
        } finally {
            setBulkApplying(false)
        }
    }

    const handleRestartPool = async () => {
        if (!confirm('Are you sure you want to restart the proxy pool?')) return
        setRestarting(true)
        try {
            await proxiesApi.reloadPool()
            toast.success('Proxy pool restarted successfully')
            await fetchData()
        } catch (error: any) {
            toast.error(error.message || 'Failed to restart proxy pool')
        } finally {
            setRestarting(false)
        }
    }

    const handleTestNode = async (id: number) => {
        setNodeOperations(prev => ({ ...prev, [id]: 'testing' }))
        try {
            await proxiesApi.testNodeLatency(id)
            toast.success('Node tested')
            await fetchData()
        } catch (error: any) {
            toast.error(error.message || 'Test failed')
        } finally {
            setNodeOperations(prev => {
                const next = { ...prev }
                delete next[id]
                return next
            })
        }
    }

    const toggleSort = (field: 'usage' | 'latency' | 'name') => {
        if (sortBy === field) {
            setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
        } else {
            setSortBy(field); setSortDir('asc')
        }
    }

    const uniqueTypes = useMemo(() => Array.from(new Set(nodes.map(n => n.node_type).filter((t): t is string => !!t))), [nodes])
    // 直接从 DB 的 region_tag 字段动态生成地域列表（支持任意国家）
    const uniqueRegions = useMemo(() => {
        const codes = new Set<string>()
        nodes.forEach(n => {
            if (n.region_tag && n.region_tag !== 'UN') codes.add(n.region_tag.toUpperCase())
        })
        return Array.from(codes).sort()
    }, [nodes])

    const filteredNodes = useMemo(() => {
        let result = [...nodes]
        if (filters.type !== 'all') result = result.filter(n => n.node_type === filters.type)
        // 直接按 region_tag 字段精确筛选
        if (filters.region !== 'all') result = result.filter(n => (n.region_tag || '').toUpperCase() === filters.region)
        if (filters.enabled !== 'all') result = result.filter(n => n.is_enabled === (filters.enabled === 'true'))

        result.sort((a, b) => {
            let cmp = 0
            switch (sortBy) {
                case 'usage': cmp = a.usage_count - b.usage_count; break
                case 'latency': cmp = (a.latency || 9999) - (b.latency || 9999); break
                case 'name': cmp = a.name.localeCompare(b.name); break
            }
            return sortDir === 'asc' ? cmp : -cmp
        })
        return result
    }, [nodes, filters, sortBy, sortDir])

    const getLatencyIcon = (latency: number | null) => {
        if (latency === null) return <Signal className="h-4 w-4 text-muted-foreground" />
        if (latency < 200) return <SignalHigh className="h-4 w-4 text-green-500" />
        if (latency < 500) return <SignalMedium className="h-4 w-4 text-yellow-500" />
        return <SignalLow className="h-4 w-4 text-red-500" />
    }

    return (
        <div className="flex-1 space-y-8 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div className="space-y-1">
                    <h1 className="text-2xl font-bold tracking-tight">{t('proxies.title')}</h1>
                    <p className="text-muted-foreground text-sm">
                        {t('proxies.subtitle')}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleRestartPool}
                        disabled={restarting}
                    >
                        <RefreshCw className={cn("mr-2 h-4 w-4", restarting && "animate-spin")} />
                        {t('proxies.restart_pool')}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleTestAll}
                        disabled={testing}
                    >
                        <Zap className={cn("mr-2 h-4 w-4", testing && "animate-ping")} />
                        {t('proxies.test')}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSync}
                        disabled={syncing}
                    >
                        <Network className={cn("mr-2 h-4 w-4", syncing && "animate-spin")} />
                        {t('proxies.sync')}
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="bg-card/30 border-border/50 overflow-hidden group hover:border-primary/20 transition-all">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground/50 flex items-center gap-2">
                            <Activity className="h-4 w-4 text-green-500" />
                            {t('proxies.clash_status')}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center justify-between">
                            <div className="text-lg font-bold">
                                {clashStatus.connected ? t('proxies.status.active') : t('proxies.status.disconnected')}
                            </div>
                            {clashStatus.connected && (
                                <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20">
                                    Online
                                </Badge>
                            )}
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-card/30 border-border/50 overflow-hidden group hover:border-primary/20 transition-all">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground/50 flex items-center gap-2">
                            <Network className="h-4 w-4 text-primary" />
                            {t('proxies.dynamic_routing')}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-bold truncate">
                            {clashStatus.current_node || t('common.none')}
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-card/30 border-border/50 overflow-hidden group hover:border-primary/20 transition-all">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground/50 flex items-center gap-2">
                            <Signal className="h-4 w-4 text-amber-500" />
                            {t('proxies.pool_status')}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-end gap-2">
                            <div className="text-2xl font-bold">{poolStatus.total}</div>
                            <div className="text-xs text-muted-foreground mb-1">
                                {t('proxies.status.active')}: {poolStatus.active} | Idle: {poolStatus.idle}
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="flex flex-col md:flex-row gap-4">
                <div className="w-full md:w-[200px]">
                    <Select value={filters.type} onValueChange={(v) => setFilters({ ...filters, type: v })}>
                        <SelectTrigger>
                            <SelectValue placeholder={t('proxies.filter.protocol')} />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">{t('proxies.filter.all')}</SelectItem>
                            {uniqueTypes.map(type => (
                                <SelectItem key={type} value={type}>{type}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="w-full md:w-[200px]">
                    <Select value={filters.region} onValueChange={(v) => setFilters({ ...filters, region: v })}>
                        <SelectTrigger>
                            <SelectValue placeholder={t('proxies.filter.region')} />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">{t('proxies.filter.all_regions')}</SelectItem>
                            {uniqueRegions.map(code => {
                                const { flag, label } = getRegionDisplay(code)
                                return (
                                    <SelectItem key={code} value={code}>
                                        <div className="flex items-center gap-2">
                                            <img src={flag} className="w-4 h-3 object-contain" alt={code} />
                                            <span>{label}</span>
                                        </div>
                                    </SelectItem>
                                )
                            })}
                        </SelectContent>
                    </Select>
                </div>
                <div className="w-full md:w-[200px]">
                    <Select value={filters.enabled} onValueChange={(v) => setFilters({ ...filters, enabled: v })}>
                        <SelectTrigger>
                            <SelectValue placeholder={t('proxies.filter.status')} />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">{t('proxies.filter.all_status')}</SelectItem>
                            <SelectItem value="true">{t('proxies.filter.active')}</SelectItem>
                            <SelectItem value="false">{t('proxies.filter.disabled')}</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            <div className="flex flex-col md:flex-row md:items-center gap-3">
                <div className="flex items-center gap-3">
                    <Switch checked={bulkMode} onCheckedChange={setBulkMode} />
                    <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Batch Mode</span>
                </div>
                {bulkMode && (
                    <div className="flex flex-wrap items-center gap-2">
                        <Button variant="outline" size="sm" onClick={handleSelectAllVisible}>
                            Select Visible
                        </Button>
                        <Button variant="outline" size="sm" onClick={clearSelection}>
                            Clear Selection
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleBulkToggle(true)}
                            disabled={bulkApplying}
                        >
                            Enable Selected ({selectedCount})
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleBulkToggle(false)}
                            disabled={bulkApplying}
                        >
                            Disable Selected ({selectedCount})
                        </Button>
                    </div>
                )}
            </div>

            <div className="rounded-md border bg-card">
                <Table>
                    <TableHeader className="bg-muted/50">
                        <TableRow className="hover:bg-transparent border-border/50">
                            {bulkMode && (
                                <TableHead className="w-[40px] text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 text-center">Sel</TableHead>
                            )}
                            <TableHead className="w-[40px] text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 text-center">{t('proxies.table.health')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 cursor-pointer" onClick={() => toggleSort('name')}>
                                {t('proxies.table.node')} <ArrowUpDown className="ml-2 h-4 w-4 inline-block" />
                            </TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 text-center">{t('proxies.table.protocol')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50">{t('proxies.table.geo')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 cursor-pointer" onClick={() => toggleSort('latency')}>
                                {t('proxies.table.latency')} <ArrowUpDown className="ml-2 h-4 w-4 inline-block" />
                            </TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 cursor-pointer text-center" onClick={() => toggleSort('usage')}>
                                {t('proxies.table.usage')} <ArrowUpDown className="ml-2 h-4 w-4 inline-block" />
                            </TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50">{t('proxies.table.status')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 text-right">{t('common.actions')}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filteredNodes.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} className="h-24 text-center">
                                    No Nodes Found
                                </TableCell>
                            </TableRow>
                        ) : (
                            filteredNodes.map(node => {
                                return (
                                    <TableRow key={node.id}>
                                        {bulkMode && (
                                            <TableCell className="text-center">
                                                <input
                                                    type="checkbox"
                                                    checked={!!selectedIds[node.id]}
                                                    onChange={() => toggleSelection(node.id)}
                                                />
                                            </TableCell>
                                        )}
                                        <TableCell className="text-center">
                                            <div className="flex items-center justify-center">
                                                <div className={`w-3 h-3 rounded-full ${node.is_healthy === true ? 'bg-green-500' :
                                                    node.is_healthy === false ? 'bg-red-500' : 'bg-gray-400'
                                                    }`} />
                                            </div>
                                        </TableCell>
                                        <TableCell className="font-medium">
                                            <div className="flex flex-col">
                                                <div className="flex items-center gap-2">
                                                    <span>{node.name}</span>
                                                    {node.source === 'external' && (
                                                        <Badge variant="outline" className="text-[10px] h-4 px-1 bg-blue-500/10 text-blue-500 border-blue-500/20">
                                                            External
                                                        </Badge>
                                                    )}
                                                </div>
                                                <span className="text-[10px] text-muted-foreground font-mono">ID: {node.id}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-center">
                                            <Badge variant="secondary">{node.node_type}</Badge>
                                        </TableCell>
                                        <TableCell>
                                            {node.region_tag && node.region_tag !== 'UN' ? (
                                                <div className="flex items-center gap-2">
                                                    <img
                                                        src={`https://flagcdn.com/w40/${node.region_tag.toLowerCase()}.png`}
                                                        className="w-5 h-4 object-contain rounded-sm"
                                                        alt={node.region_tag}
                                                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                                                    />
                                                    <span className="text-xs font-mono font-semibold">{node.region_tag}</span>
                                                </div>
                                            ) : '--'}
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {nodeOperations[node.id] === 'testing' ? (
                                                    <>
                                                        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                                                        <span className="text-muted-foreground italic">Test...</span>
                                                    </>
                                                ) : (
                                                    <>
                                                        {getLatencyIcon(node.latency ?? null)}
                                                        <span>{node.latency ? `${node.latency}ms` : 'N/A'}</span>
                                                    </>
                                                )}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-center">
                                            <span className="font-mono text-xs">{node.usage_count || 0}</span>
                                        </TableCell>
                                        <TableCell>
                                            {nodeOperations[node.id] === 'toggling' ? (
                                                <div className="flex items-center gap-1.5 opacity-70">
                                                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                                </div>
                                            ) : (
                                                <Switch
                                                    checked={node.is_enabled}
                                                    onCheckedChange={() => handleToggle(node.id)}
                                                    className="scale-110"
                                                />
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 hover:bg-blue-500/10 hover:text-blue-500"
                                                    onClick={() => handleTestNode(node.id)}
                                                    disabled={nodeOperations[node.id] === 'testing' || testing}
                                                >
                                                    {nodeOperations[node.id] === 'testing' ? (
                                                        <Loader2 className="h-4 w-4 animate-spin" />
                                                    ) : (
                                                        <Zap className="h-4 w-4" />
                                                    )}
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow >
                                )
                            })
                        )}
                    </TableBody >
                </Table >
            </div >
        </div >
    )
}
