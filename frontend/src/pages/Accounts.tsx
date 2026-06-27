import { useEffect, useState, useRef } from 'react'
import {
    Trash2,
    Copy,
    CheckCircle,
    Download,
    Eye,
    EyeOff,
    MoreHorizontal,
    Search,
    RefreshCw,
    Chrome,
    Calendar,
    ArrowRight,
    Loader2,
    ZapOff,
    CheckCircle2,
    Power,
    Upload
} from 'lucide-react'
import { toast } from 'sonner'
import { accountsApi, Account, AccountStats } from '../services/api'
import { REGION_MAP, parseRegion as parseRegionUtil } from '@/lib/constants'
import { cn } from '@/lib/utils'
import { useLanguage } from '@/contexts/LanguageContext'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"



import { GlassDatePicker } from "@/components/ui/glass-date-picker"

// Module-level caches to prevent UI clear flickering during navigations
let cachedAccounts: Account[] = []
let cachedStats: AccountStats | null = null
let cachedFilters = {
    status: 'all',
    health_status: 'all',
    region: 'all',
    usage_status: 'all',
    start_date: '',
    end_date: ''
}
let cachedSearchQuery = ''

export default function Accounts() {
    const [accounts, setAccounts] = useState<Account[]>(cachedAccounts)
    const [stats, setStats] = useState<AccountStats | null>(cachedStats)
    const [loading, setLoading] = useState(cachedAccounts.length === 0)
    const [searchQuery, setSearchQuery] = useState(cachedSearchQuery)

    // Filter State
    const [filters, setFilters] = useState(cachedFilters)

    const [copiedId, setCopiedId] = useState<number | null>(null)
    const [showPasswordId, setShowPasswordId] = useState<number | null>(null)
    const [actionState, setActionState] = useState<{ id: number; type: 'refresh' | 'checkin' | 'login' | 'gen_toggle' } | null>(null)
    const { t } = useLanguage()
    const [manualOpen, setManualOpen] = useState(false)
    const [importOpen, setImportOpen] = useState(false)
    const [manualEmail, setManualEmail] = useState('')
    const [manualRegion, setManualRegion] = useState('')
    const [manualSession, setManualSession] = useState('')
    const [importContent, setImportContent] = useState('')
    const [importBusy, setImportBusy] = useState(false)
    const [importFileName, setImportFileName] = useState('')
    const [importDragActive, setImportDragActive] = useState(false)

    useEffect(() => {
        fetchStats()
    }, [])

    useEffect(() => {
        const timer = setTimeout(() => {
            fetchAccounts(true)
            fetchStats()
        }, 300)
        return () => clearTimeout(timer)
    }, [filters, searchQuery])

    const fetchStats = async () => {
        try {
            const params: any = {
                search: searchQuery || undefined
            }
            if (filters.status !== 'all') params.status = filters.status
            if (filters.health_status !== 'all') params.health_status = filters.health_status
            if (filters.region !== 'all') params.region = filters.region
            if (filters.usage_status !== 'all') params.usage_status = filters.usage_status
            if (filters.start_date) params.start_date = filters.start_date
            if (filters.end_date) params.end_date = filters.end_date

            const data = await accountsApi.getStats(params)
            cachedStats = data
            setStats(data)
        } catch (err) {
            console.error('Failed to fetch stats:', err)
        }
    }

    const fetchAccounts = async (silent = false) => {
        try {
            if (!silent) setLoading(true)
            const params: any = {
                search: searchQuery || undefined,
                page_size: 5000 // Load more to ensure 100+ items appear and match exported stats
            }

            if (filters.status !== 'all') params.status = filters.status
            if (filters.health_status !== 'all') params.health_status = filters.health_status
            if (filters.region !== 'all') params.region = filters.region
            if (filters.usage_status !== 'all') params.usage_status = filters.usage_status
            if (filters.start_date) params.start_date = filters.start_date
            if (filters.end_date) params.end_date = filters.end_date

            const data = await accountsApi.list(params)
            cachedAccounts = data
            setAccounts(data)
        } catch (error) {
            toast.error('Failed to fetch accounts')
            console.error(error)
        } finally {
            setLoading(false)
        }
    }

    // Keep cache synced when filter changes
    useEffect(() => {
        cachedFilters = filters
    }, [filters])

    useEffect(() => {
        cachedSearchQuery = searchQuery
    }, [searchQuery])

    // --- WebSocket Listener for Auto Refresh ---
    const fetchAccountsRef = useRef(fetchAccounts)
    const fetchStatsRef = useRef(fetchStats)

    useEffect(() => {
        fetchAccountsRef.current = fetchAccounts
        fetchStatsRef.current = fetchStats
    })

    useEffect(() => {
        let ws: WebSocket | null = null
        let reconnectTimeout: any = null

        const connect = () => {
            // Check if we are running locally in dev mode or in production
            const host = window.location.port === '5175' || window.location.port === '3000'
                ? 'localhost:8005'
                : window.location.host
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'

            try {
                ws = new WebSocket(`${protocol}//${host}/ws/logs`)

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data)
                        if (data.type === 'log' && data.message && (
                            data.message.includes('已自动更新账号') ||
                            data.message.includes('Session ID')
                        )) {
                            // Backend emitted a log indicating session_id was updated
                            fetchAccountsRef.current(true)
                            fetchStatsRef.current()
                        }
                    } catch (e) { }
                }

                ws.onclose = () => {
                    reconnectTimeout = setTimeout(connect, 5000)
                }
            } catch (err) {
                console.error('WebSocket connection failed', err)
            }
        }

        connect()

        return () => {
            if (reconnectTimeout) clearTimeout(reconnectTimeout)
            if (ws) {
                ws.onclose = null
                ws.close()
            }
        }
    }, [])
    // -------------------------------------------

    const handleCopy = async (text: string, id: number) => {
        await navigator.clipboard.writeText(text)
        setCopiedId(id)
        setTimeout(() => setCopiedId(null), 2000)
    }

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this account?')) return
        try {
            await accountsApi.delete(id)
            toast.success('Account deleted')
            fetchAccounts(true)
            fetchStats()
        } catch (error: any) {
            toast.error(error.message || 'Failed to delete account')
        }
    }

    const handleExport = (format: 'csv' | 'json') => {
        const params: any = { format, search: searchQuery || undefined }
        if (filters.status !== 'all') params.status = filters.status
        if (filters.health_status !== 'all') params.health_status = filters.health_status
        if (filters.region !== 'all') params.region = filters.region
        if (filters.usage_status !== 'all') params.usage_status = filters.usage_status
        if (filters.start_date) params.start_date = filters.start_date
        if (filters.end_date) params.end_date = filters.end_date
        accountsApi.export(params)
        toast.success(`Exporting ${format.toUpperCase()}...`)
    }

    const handleGenToggle = async (account: Account, enabled: boolean) => {
        setActionState({ id: account.id, type: 'gen_toggle' })
        try {
            await accountsApi.toggleGeneration(account.id, enabled)
            toast.success(enabled ? 'Token Pool Enabled' : 'Token Pool Disabled')
            fetchAccounts(true)
        } catch (error: any) {
            toast.error(error.message || 'Failed to toggle token pool')
        } finally {
            setActionState(null)
        }
    }

    const handleManualCreate = async () => {
        const email = manualEmail.trim()
        const region = manualRegion.trim()
        const sessionId = manualSession.trim()
        if (!email || !region || !sessionId) {
            toast.error('请填写邮箱、地域、sessionid')
            return
        }
        try {
            await accountsApi.manualCreate({ email, region, session_id: sessionId })
            toast.success('账号已添加并加入生成池')
            setManualOpen(false)
            setManualEmail('')
            setManualRegion('')
            setManualSession('')
            fetchAccounts(true)
            fetchStats()
        } catch (err: any) {
            const msg = err?.message || '添加失败'
            toast.error(msg)
        }
    }

    const detectImportMode = (text: string) => {
        const trimmed = text.trim()
        if (!trimmed) return 'txt' as const
        const firstLine = trimmed.split(/\r?\n/)[0] || ''
        const lower = firstLine.toLowerCase()
        if (lower.includes('email') && lower.includes('region') && lower.includes('session')) return 'csv' as const
        if (firstLine.includes(',') && lower.includes('email')) return 'csv' as const
        return 'txt' as const
    }

    const handleImportSubmit = async () => {
        const content = importContent.trim()
        if (!content) {
            toast.error('请粘贴或上传导入内容')
            return
        }
        const mode = detectImportMode(content)
        setImportBusy(true)
        try {
            const result = await accountsApi.manualImport({ mode, content })
            const summary = `成功 ${result.success} / 跳过 ${result.skipped} / 失败 ${result.failed}`
            if (result.failed > 0) {
                toast.error(`导入完成：${summary}`)
            } else {
                toast.success(`导入完成：${summary}`)
            }
            setImportOpen(false)
            setImportContent('')
            setImportFileName('')
            fetchAccounts(true)
            fetchStats()
        } catch (err: any) {
            const msg = err?.message || '导入失败'
            toast.error(msg)
        } finally {
            setImportBusy(false)
        }
    }

    const handleImportFile = async (file: File | null) => {
        if (!file) return
        try {
            const text = await file.text()
            setImportContent(text)
            setImportFileName(file.name)
        } catch (err) {
            toast.error('读取文件失败')
        }
    }

    const handleBatchGenToggle = async (enabled: boolean) => {
        try {
            const params: any = {
                is_enabled: enabled,
                search: searchQuery || undefined,
                status: filters.status !== 'all' ? filters.status : undefined,
                health_status: filters.health_status !== 'all' ? filters.health_status : undefined,
                region: filters.region !== 'all' ? filters.region : undefined,
                usage_status: filters.usage_status !== 'all' ? filters.usage_status : undefined,
                start_date: filters.start_date || undefined,
                end_date: filters.end_date || undefined,
            }
            await accountsApi.batchToggleGeneration(params)
            toast.success(enabled ? 'Successfully Enabled All' : 'Successfully Disabled All')
            await fetchAccounts(true)
        } catch (error: any) {
            toast.error(error.message || 'Failed to update token pool')
        }
    }

    const getUsageBadge = (account: Account) => {
        if (!account.gen_enabled) {
            return (
                <div className="flex items-center gap-1.5 text-muted-foreground">
                    <ZapOff className="h-3.5 w-3.5" />
                    <span className="text-xs">禁用</span>
                </div>
            )
        }
        const now = new Date()
        const lockedUntil = account.gen_locked_until ? new Date(account.gen_locked_until) : null
        const inUse = lockedUntil && lockedUntil > now
        if (inUse) {
            return (
                <div className="flex items-center gap-1.5 text-orange-500">
                    <div className="relative flex h-3 w-3 items-center justify-center">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span>
                    </div>
                    <span className="text-xs font-medium">使用中</span>
                </div>
            )
        }
        return (
            <div className="flex items-center gap-1.5 text-green-500">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span className="text-xs font-medium">空闲</span>
            </div>
        )
    }

    const handleLogin = async (account: Account) => {
        // 取消了前端只能用 session_id 登录的限制
        // 后端会通过是否拥有 browser_state_path 来拦截并提示
        try {
            toast.promise(fetch(`/api/accounts/${account.id}/login`, { method: 'POST' }), {
                loading: 'Launching browser...',
                success: 'Browser launched',
                error: (err) => err.message || 'Launch failed'
            })
        } catch (error) {
            toast.error('Failed to connect to browser service')
        }
    }

    const handleRefreshStatus = async (id: number) => {
        setActionState({ id, type: 'refresh' })
        try {
            await accountsApi.refreshStatus(id)
            toast.success('Status refreshed')
            fetchAccounts(true)
        } catch (error: any) {
            toast.error(error.message || 'Refresh failed')
        } finally {
            setActionState(null)
        }
    }

    const handleCheckin = async (id: number) => {
        setActionState({ id, type: 'checkin' })
        try {
            await accountsApi.checkin(id)
            toast.success('Check-in successful')
            fetchAccounts(true)
        } catch (error: any) {
            toast.error(error.message || 'Check-in failed')
        } finally {
            setActionState(null)
        }
    }

    const handleBatchRefresh = async () => {
        if (accounts.length === 0) return
        const ids = accounts.map(a => a.id)

        toast.promise(accountsApi.batchRefreshStatus(ids), {
            loading: 'Refreshing accounts...',
            success: (res) => {
                fetchAccounts(true)
                return res.message
            },
            error: 'Batch refresh failed'
        })
    }

    const handleBatchCheckin = async () => {
        if (accounts.length === 0) return
        const ids = accounts.map(a => a.id)

        toast.promise(accountsApi.batchCheckin(ids), {
            loading: 'Performing check-in...',
            success: (res) => {
                fetchAccounts(true)
                return res.message
            },
            error: 'Batch check-in failed'
        })
    }

    const handleBatchDelete = async () => {
        if (accounts.length === 0) return
        if (!confirm(`Delete ${accounts.length} accounts?`)) return

        const ids = accounts.map(a => a.id)
        toast.promise(accountsApi.batchDelete(ids), {
            loading: 'Deleting accounts...',
            success: (res) => {
                fetchAccounts(true)
                fetchStats()
                return res.message
            },
            error: 'Batch delete failed'
        })
    }

    const getStatusBadge = (account: Account) => {
        const status = account.status
        const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
            pending: 'secondary',
            registering: 'secondary',
            success: 'default',
            active: 'default',
            failed: 'destructive',
            banned: 'destructive'
        }

        const isSuccess = status === 'success' || status === 'active'
        const className = isSuccess ? 'bg-green-500 hover:bg-green-600' :
            status === 'registering' ? 'bg-blue-500 hover:bg-blue-600 text-white' : undefined

        const label = isSuccess ? 'SUCCESS' : status.toUpperCase()

        return <Badge variant={variants[status] || 'outline'} className={className}>{label}</Badge>
    }

    const getRegionDisplay = (regionCode: string | undefined) => {
        if (!regionCode) return <span className="text-muted-foreground text-xs">--</span>

        const upperCode = regionCode.toUpperCase()
        const region = REGION_MAP[upperCode] || parseRegionUtil(regionCode)

        if (!region) return <span className="text-muted-foreground text-xs">{regionCode}</span>

        return (
            <div className="flex items-center gap-2">
                <img
                    src={region.flag}
                    alt={region.name}
                    className="w-4 h-auto rounded-sm shadow-sm"
                    onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none'
                    }}
                />
                <span className="text-xs font-medium">{region.name}</span>
            </div>
        )
    }

    const sortedAccounts = accounts // Backend already sorts by created_at



    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div className="space-y-1">
                    <h1 className="text-2xl font-bold tracking-tight">{t('accounts.title')}</h1>
                    <p className="text-muted-foreground text-sm">
                        {t('accounts.subtitle')}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setManualOpen(true)}
                    >
                        手动添加
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setImportOpen(true)}
                    >
                        批量导入
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBatchRefresh}
                        disabled={loading}
                    >
                        <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />
                        {t('accounts.batch_refresh')}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBatchCheckin}
                        disabled={loading}
                    >
                        <Calendar className="mr-2 h-4 w-4" />
                        {t('accounts.batch_checkin')}
                    </Button>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm">
                                <Download className="mr-2 h-4 w-4" />
                                {t('accounts.export')}
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleExport('csv')}>CSV</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleExport('json')}>JSON</DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleBatchDelete}
                        disabled={loading || accounts.length === 0}
                    >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {t('accounts.batch_delete')}
                    </Button>
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/30 rounded-md border border-border/50">
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs px-3 text-green-500 hover:text-green-600 hover:bg-green-500/10 border-green-500/20"
                            onClick={() => handleBatchGenToggle(true)}
                            disabled={loading || accounts.length === 0}
                        >
                            全部启用
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs px-3 text-red-500 hover:text-red-600 hover:bg-red-500/10 border-red-500/20"
                            onClick={() => handleBatchGenToggle(false)}
                            disabled={loading || accounts.length === 0}
                        >
                            全部禁用
                        </Button>
                    </div>
                </div>
            </div>

            <div className="flex flex-col md:flex-row gap-4 items-center">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder={t('common.search') + "..."}
                        className="pl-10 h-9 bg-background/50 border-border/50 focus:bg-background transition-all"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="flex items-center gap-2 bg-muted/20 p-1 rounded-lg border border-border/30">
                    <GlassDatePicker
                        value={filters.start_date}
                        onChange={(v) => setFilters({ ...filters, start_date: v })}
                        placeholder={t('accounts.filter.start_date') || "Start Date"}
                        className="w-[140px]"
                    />
                    <ArrowRight className="h-3 w-3 text-muted-foreground/50" />
                    <GlassDatePicker
                        value={filters.end_date}
                        onChange={(v) => setFilters({ ...filters, end_date: v })}
                        placeholder={t('accounts.filter.end_date') || "End Date"}
                        className="w-[140px]"
                    />
                </div>
                <div className="w-[160px]">
                    <Select value={filters.status} onValueChange={(v) => setFilters({ ...filters, status: v })}>
                        <SelectTrigger className="h-9 bg-transparent border-border/50">
                            <SelectValue placeholder={t('accounts.filter.status')} />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">{t('accounts.status.all')}</SelectItem>
                            <SelectItem value="success">{t('accounts.status.success')}</SelectItem>
                            <SelectItem value="failed">{t('accounts.status.failed')}</SelectItem>
                            <SelectItem value="pending">{t('accounts.status.pending')}</SelectItem>
                            <SelectItem value="banned">{t('accounts.status.banned')}</SelectItem>
                            <SelectItem value="active">{t('accounts.status.active')}</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="w-[140px]">
                    <Select value={filters.health_status} onValueChange={(v) => setFilters({ ...filters, health_status: v })}>
                        <SelectTrigger className="h-9 bg-transparent border-border/50">
                            <SelectValue placeholder={t('accounts.filter.health')} />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">{t('accounts.health.all')}</SelectItem>
                            <SelectItem value="healthy">{t('accounts.health.healthy')}</SelectItem>
                            <SelectItem value="expired">{t('accounts.health.expired')}</SelectItem>
                            <SelectItem value="unknown">{t('accounts.health.unknown')}</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="w-[140px]">
                    <Select value={filters.region} onValueChange={(v) => setFilters({ ...filters, region: v })}>
                        <SelectTrigger className="h-9 bg-transparent border-border/50">
                            <SelectValue placeholder={t('accounts.filter.region')} />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">{t('accounts.region.all')}</SelectItem>
                            {Object.entries(REGION_MAP).map(([code, reg]) => (
                                <SelectItem key={code} value={code.toLowerCase()}>
                                    {useLanguage().language === 'zh' ? reg.name : code}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <div className="w-[140px]">
                    <Select value={filters.usage_status} onValueChange={(v) => setFilters({ ...filters, usage_status: v })}>
                        <SelectTrigger className="h-9 bg-transparent border-border/50">
                            <SelectValue placeholder="使用状态" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">全部</SelectItem>
                            <SelectItem value="in_use">使用中</SelectItem>
                            <SelectItem value="idle">空闲</SelectItem>
                            <SelectItem value="disabled">禁用</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="ml-auto flex items-center gap-10 text-sm font-medium">
                    <div className="flex items-center gap-2">
                        <span className="text-muted-foreground/60">{useLanguage().language === 'zh' ? '总数：' : 'Total: '}</span>
                        <span className="text-white tabular-nums font-bold text-base">{stats?.total || 0}</span>
                    </div>
                    {(filters.status !== 'all' || filters.health_status !== 'all' || filters.region !== 'all' || filters.usage_status !== 'all' || filters.start_date || filters.end_date || searchQuery) && (
                        <div className="flex items-center gap-2 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                            <div className="w-[1px] h-3.5 bg-border/40 mx-2" />
                            <span className="text-muted-foreground/60">{useLanguage().language === 'zh' ? '匹配：' : 'Matches: '}</span>
                            <span className={cn(
                                "tabular-nums font-bold text-base transition-colors",
                                (stats?.matched || 0) > 0 ? "text-green-500" : "text-muted-foreground/40"
                            )}>
                                {stats?.matched ?? 0}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            <div className="rounded-xl border border-border/10 bg-card overflow-hidden">
                <Table>
                    <TableHeader className="bg-muted/30">
                        <TableRow>
                            <TableHead className="py-4">{t('accounts.table.account')}</TableHead>
                            <TableHead>{t('accounts.table.password')}</TableHead>
                            <TableHead>{t('accounts.table.task_id')}</TableHead>
                            <TableHead>{t('accounts.table.region')}</TableHead>
                            <TableHead>{t('accounts.table.health')}</TableHead>
                            <TableHead>{t('accounts.table.session')}</TableHead>
                            <TableHead className="text-right">{t('accounts.table.credits')}</TableHead>
                            <TableHead className="text-center">使用状态</TableHead>
                            <TableHead className="text-right">{t('accounts.table.created')}</TableHead>
                            <TableHead className="w-[100px] text-center">{t('accounts.table.status')}</TableHead>
                            <TableHead className="text-right">{t('common.actions')}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={10} className="h-32 text-center">
                                    <div className="flex flex-col items-center justify-center gap-2">
                                        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground/30" />
                                        <span className="text-sm text-muted-foreground">Loading accounts...</span>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ) : sortedAccounts.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={10} className="h-32 text-center text-muted-foreground italic">
                                    No accounts found matching current filters.
                                </TableCell>
                            </TableRow>
                        ) : (
                            sortedAccounts.map((account) => (
                                <TableRow key={account.id}>
                                    <TableCell>
                                        <div className="flex flex-col">
                                            <span className="font-medium">{account.email}</span>
                                            <span className="text-xs text-muted-foreground">ID: {account.id}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-2">
                                            <span className="font-mono text-xs">
                                                {showPasswordId === account.id ? account.password : '••••••••'}
                                            </span>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6"
                                                onClick={() => setShowPasswordId(showPasswordId === account.id ? null : account.id)}
                                            >
                                                {showPasswordId === account.id ? (
                                                    <EyeOff className="h-3 w-3" />
                                                ) : (
                                                    <Eye className="h-3 w-3" />
                                                )}
                                            </Button>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <span className="font-mono text-[10px] text-muted-foreground">
                                            {account.task_id?.split('-')[0] || '--'}
                                        </span>
                                    </TableCell>
                                    <TableCell>{getRegionDisplay(account.region || account.proxy_node_name || undefined)}</TableCell>
                                    <TableCell>
                                        {actionState?.id === account.id && actionState?.type === 'refresh' ? (
                                            <Badge variant="outline" className="bg-muted text-muted-foreground flex items-center gap-1.5 w-fit py-0 text-[10px]">
                                                <Loader2 className="h-2.5 w-2.5 animate-spin" />
                                                REFRESHING...
                                            </Badge>
                                        ) : (
                                            <Badge
                                                variant="outline"
                                                className={cn(
                                                    'text-[10px] py-0',
                                                    account.health_status === 'healthy' ? 'text-green-500 border-green-500/20 bg-green-500/10' :
                                                        account.health_status === 'expired' ? 'text-amber-500 border-amber-500/20 bg-amber-500/10' :
                                                            'text-muted-foreground'
                                                )}
                                            >
                                                {(account.health_status || 'unknown').toUpperCase()}
                                            </Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {account.session_id ? (
                                            <div className="flex items-center gap-2">
                                                <span className="font-mono text-xs text-muted-foreground truncate max-w-[100px]">
                                                    {account.session_id}
                                                </span>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-6 w-6"
                                                    onClick={() => handleCopy(account.session_id!, account.id)}
                                                >
                                                    {copiedId === account.id ? (
                                                        <CheckCircle className="h-3 w-3 text-green-500" />
                                                    ) : (
                                                        <Copy className="h-3 w-3" />
                                                    )}
                                                </Button>
                                            </div>
                                        ) : (
                                            <span className="text-xs text-muted-foreground">--</span>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        {actionState?.id === account.id && (actionState?.type === 'checkin' || actionState?.type === 'refresh') ? (
                                            <div className="flex items-center justify-end gap-1.5 text-muted-foreground text-xs">
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                                <span>{actionState?.type === 'checkin' ? 'Claiming...' : 'Updating...'}</span>
                                            </div>
                                        ) : (
                                            <div className="flex flex-col items-end">
                                                <span className="font-bold">{account.credits_total || 0}</span>
                                                {account.credits_gift > 0 && (
                                                    <span className="text-xs text-amber-500">+{account.credits_gift}</span>
                                                )}
                                            </div>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <div className="flex justify-center">
                                            {getUsageBadge(account)}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <span className="text-xs text-muted-foreground">
                                            {new Date(account.created_at).toLocaleString('zh-CN', { hour12: false })}
                                        </span>
                                    </TableCell>
                                    <TableCell>{getStatusBadge(account)}</TableCell>
                                    <TableCell>
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" className="h-8 w-8 p-0">
                                                    <span className="sr-only">Open menu</span>
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end">
                                                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                                                <DropdownMenuItem
                                                    onClick={() => handleLogin(account)}
                                                    disabled={account.status === 'registering' || account.status === 'pending'}
                                                >
                                                    <Chrome className="mr-2 h-4 w-4" /> Login
                                                </DropdownMenuItem>
                                                <DropdownMenuItem onClick={() => navigator.clipboard.writeText(account.email)}>
                                                    <Copy className="mr-2 h-4 w-4" /> Copy Email
                                                </DropdownMenuItem>
                                                <DropdownMenuSeparator />
                                                <DropdownMenuItem
                                                    onClick={() => handleRefreshStatus(account.id)}
                                                    disabled={actionState?.id === account.id}
                                                >
                                                    <RefreshCw className={cn("mr-2 h-4 w-4", actionState?.id === account.id && actionState.type === 'refresh' && "animate-spin")} />
                                                    Refresh Status
                                                </DropdownMenuItem>
                                                <DropdownMenuItem 
                                                    onClick={() => handleGenToggle(account, !account.gen_enabled)}
                                                    disabled={actionState?.id === account.id}
                                                >
                                                    <Power className="mr-2 h-4 w-4" />
                                                    <span className={account.gen_enabled ? "text-red-500" : "text-green-500"}>
                                                        {account.gen_enabled ? "禁用 TOKEN" : "启用 TOKEN"}
                                                    </span>
                                                </DropdownMenuItem>
                                                <DropdownMenuItem
                                                    onClick={() => handleCheckin(account.id)}
                                                    disabled={actionState?.id === account.id}
                                                >
                                                    <Calendar className={cn("mr-2 h-4 w-4", actionState?.id === account.id && actionState.type === 'checkin' && "animate-pulse")} />
                                                    Check-in
                                                </DropdownMenuItem>
                                                <DropdownMenuSeparator />
                                                <DropdownMenuItem
                                                    className="text-red-600"
                                                    onClick={() => handleDelete(account.id)}
                                                    disabled={actionState?.id === account.id}
                                                >
                                                    <Trash2 className="mr-2 h-4 w-4" /> Delete
                                                </DropdownMenuItem>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>

            <Dialog open={manualOpen} onOpenChange={setManualOpen}>
                <DialogContent className="sm:max-w-[520px]">
                    <DialogHeader>
                        <DialogTitle>手动添加账号</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm text-muted-foreground">注册邮箱</label>
                            <Input value={manualEmail} onChange={(e) => setManualEmail(e.target.value)} placeholder="name@example.com" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm text-muted-foreground">地域</label>
                            <Input value={manualRegion} onChange={(e) => setManualRegion(e.target.value)} placeholder="US / JP / CN" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm text-muted-foreground">sessionid</label>
                            <Input value={manualSession} onChange={(e) => setManualSession(e.target.value)} placeholder="sessionid" />
                        </div>
                        <div className="flex justify-end gap-2">
                            <Button variant="outline" onClick={() => setManualOpen(false)}>取消</Button>
                            <Button onClick={handleManualCreate}>确认添加</Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            <Dialog open={importOpen} onOpenChange={setImportOpen}>
                <DialogContent className="sm:max-w-[720px]">
                    <DialogHeader>
                        <DialogTitle>批量导入账号</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">支持 CSV / TXT 自动识别</p>
                        <p className="text-sm text-muted-foreground">CSV 表头字段：email, region, sessionid</p>
                        <p className="text-sm text-muted-foreground">TXT 格式：email--地域--sessionid（一行一个）</p>
                    </div>
                    <div className="space-y-3">
                        <label
                            className={cn(
                                "group relative w-full h-48 rounded-2xl border border-dashed border-white/10 bg-black/40 flex flex-col items-center justify-center gap-2 text-center cursor-pointer transition-all",
                                importDragActive && "border-emerald-500/80 shadow-[0_0_20px_rgba(16,185,129,0.25)]"
                            )}
                            onDragOver={(e) => {
                                e.preventDefault()
                                setImportDragActive(true)
                            }}
                            onDragLeave={() => setImportDragActive(false)}
                            onDrop={(e) => {
                                e.preventDefault()
                                setImportDragActive(false)
                                const file = e.dataTransfer.files?.[0]
                                handleImportFile(file || null)
                            }}
                        >
                            <input
                                type="file"
                                accept=".csv,.txt"
                                className="hidden"
                                onChange={(e) => handleImportFile(e.target.files?.[0] || null)}
                            />
                            <div className="flex items-center justify-center h-14 w-14 rounded-full bg-white/5 border border-white/10 text-white/70 group-hover:text-white">
                                <Upload className="h-6 w-6" />
                            </div>
                            <div className="text-sm text-white/80">拖拽文件到这里，或点击上传</div>
                            <div className="text-xs text-muted-foreground">
                                {importFileName ? `已选择：${importFileName}` : `支持 CSV / TXT 格式`}
                            </div>
                        </label>
                        <Textarea
                            value={importContent}
                            onChange={(e) => setImportContent(e.target.value)}
                            placeholder={'email,region,sessionid\n... 或 email--region--sessionid\n...'}
                            className="min-h-[200px]"
                        />
                    </div>
                    <div className="flex justify-end gap-2">
                        <Button variant="outline" onClick={() => setImportOpen(false)}>取消</Button>
                        <Button onClick={handleImportSubmit} disabled={importBusy}>
                            {importBusy ? '导入中...' : '开始导入'}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
