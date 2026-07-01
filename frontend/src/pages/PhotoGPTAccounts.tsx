import { useEffect, useState } from 'react'
import {
    Trash2,
    MoreHorizontal,
    Search,
    RefreshCw,
    Sparkles,
    Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import { photogptAccountsApi, PhotoGPTAccount } from '../services/api'
import { cn } from '@/lib/utils'
import { useLanguage } from '@/contexts/LanguageContext'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
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
import { Card, CardContent } from "@/components/ui/card"

// Module-level cache
let cachedAccounts: PhotoGPTAccount[] = []
let cachedFilterStatus = 'all'

export default function PhotoGPTAccounts() {
    const [accounts, setAccounts] = useState<PhotoGPTAccount[]>(cachedAccounts)
    const [loading, setLoading] = useState(cachedAccounts.length === 0)
    const [searchQuery, setSearchQuery] = useState('')
    const [filterStatus, setFilterStatus] = useState(cachedFilterStatus)
    const [copiedId, setCopiedId] = useState<number | null>(null)
    const [registering, setRegistering] = useState(false)
    const [batchRegistering, setBatchRegistering] = useState(false)
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
    const { t } = useLanguage()

    useEffect(() => {
        fetchAccounts()
    }, [filterStatus])

    const fetchAccounts = async () => {
        setLoading(true)
        try {
            const data = await photogptAccountsApi.list({
                status: filterStatus !== 'all' ? filterStatus : undefined,
            })
            cachedAccounts = data
            setAccounts(data)
        } catch (error) {
            toast.error('获取 PhotoGPT 账号失败')
            console.error(error)
        } finally {
            setLoading(false)
        }
    }

    const handleDelete = async (id: number) => {
        if (!confirm(t('common.confirm_delete'))) return
        try {
            await photogptAccountsApi.delete(id)
            toast.success('已删除')
            fetchAccounts()
        } catch (error: any) {
            toast.error(error.message || '删除失败')
        }
    }

    const handleCopy = async (text: string, id: number) => {
        await navigator.clipboard.writeText(text)
        setCopiedId(id)
        setTimeout(() => setCopiedId(null), 2000)
    }

    const handleAutoRegister = async () => {
        setRegistering(true)
        try {
            const result = await photogptAccountsApi.autoRegister()
            if (result.success) {
                toast.success(`注册成功: ${result.email} (池子共 ${result.pool_total} 个账号)`)
                fetchAccounts()
            } else {
                toast.error(result.error || '注册失败')
            }
        } catch (error: any) {
            toast.error(error.message || '注册请求失败')
        } finally {
            setRegistering(false)
        }
    }

    const handleBatchRegister = async () => {
        setBatchRegistering(true)
        try {
            const result = await photogptAccountsApi.autoRegisterBatch(3)
            toast.success(`批量注册完成: ${result.success}/${result.total} 成功`)
            fetchAccounts()
        } catch (error: any) {
            toast.error(error.message || '批量注册失败')
        } finally {
            setBatchRegistering(false)
        }
    }

    const handleBatchDelete = async () => {
        if (selectedIds.size === 0) return
        if (!confirm(`确定删除 ${selectedIds.size} 个账号吗？`)) return
        try {
            const result = await photogptAccountsApi.batchDelete(Array.from(selectedIds))
            toast.success(`已删除 ${result.deleted} 个账号`)
            setSelectedIds(new Set())
            fetchAccounts()
        } catch (error: any) {
            toast.error(error.message || '批量删除失败')
        }
    }

    const toggleSelect = (id: number) => {
        const next = new Set(selectedIds)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        setSelectedIds(next)
    }

    const toggleSelectAll = () => {
        if (selectedIds.size === filteredAccounts.length) {
            setSelectedIds(new Set())
        } else {
            setSelectedIds(new Set(filteredAccounts.map(a => a.id)))
        }
    }

    const statusBadge = (status: string) => {
        const variants: Record<string, string> = {
            active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
            expired: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
            banned: 'bg-red-500/20 text-red-400 border-red-500/30',
        }
        return variants[status] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }

    const statusLabel = (status: string) => {
        const labels: Record<string, string> = {
            active: t('photogpt.accounts.status.active'),
            expired: t('photogpt.accounts.status.expired'),
            banned: t('photogpt.accounts.status.banned'),
        }
        return labels[status] || status
    }

    const filteredAccounts = searchQuery
        ? accounts.filter(a => a.email.toLowerCase().includes(searchQuery.toLowerCase()))
        : accounts

    return (
        <div className="flex-1 space-y-6 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">{t('photogpt.accounts.title')}</h2>
                    <p className="text-muted-foreground">{t('photogpt.accounts.subtitle')}</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={fetchAccounts} disabled={loading} className="h-9 border-white/5 bg-card/40 rounded-[10px]">
                        <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />
                        {t('common.sync')}
                    </Button>
                    <Button
                        size="sm"
                        onClick={handleAutoRegister}
                        disabled={registering}
                        className="h-9 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white rounded-[10px] shadow-lg shadow-emerald-500/20"
                    >
                        {registering ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="mr-2 h-4 w-4" />
                        )}
                        {registering ? '注册中...' : '添加账号'}
                    </Button>
                    <Button
                        size="sm"
                        onClick={handleBatchRegister}
                        disabled={batchRegistering}
                        className="h-9 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-400 hover:to-purple-500 text-white rounded-[10px] shadow-lg shadow-purple-500/20"
                    >
                        {batchRegistering ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="mr-2 h-4 w-4" />
                        )}
                        {batchRegistering ? '批量注册中(3)...' : '批量注册 3 个'}
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: '全部', value: accounts.length, color: 'text-sky-400' },
                    { label: t('photogpt.accounts.status.active'), value: accounts.filter(a => a.status === 'active').length, color: 'text-emerald-400' },
                    { label: t('photogpt.accounts.status.expired'), value: accounts.filter(a => a.status === 'expired').length, color: 'text-amber-400' },
                    { label: t('photogpt.accounts.status.banned'), value: accounts.filter(a => a.status === 'banned').length, color: 'text-red-400' },
                ].map((stat) => (
                    <Card key={stat.label} className="border border-white/5 bg-card/40 backdrop-blur rounded-[1.5rem]">
                        <CardContent className="p-4 flex items-center gap-3">
                            <div className={cn("text-2xl font-bold", stat.color)}>{stat.value}</div>
                            <div className="text-xs text-muted-foreground">{stat.label}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Filters */}
            <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder={t('common.search')}
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        className="pl-10 h-9 bg-card/40 border-white/5 rounded-[10px]"
                    />
                </div>
                <Select value={filterStatus} onValueChange={v => { setFilterStatus(v); cachedFilterStatus = v }}>
                    <SelectTrigger className="w-[130px] h-9 bg-card/40 border-white/5 rounded-[10px]">
                        <SelectValue placeholder={t('common.all')} />
                    </SelectTrigger>
                    <SelectContent className="border-white/10 bg-black/90 backdrop-blur-xl rounded-[10px]">
                        <SelectItem value="all">{t('common.all')}</SelectItem>
                        <SelectItem value="active">{t('photogpt.accounts.status.active')}</SelectItem>
                        <SelectItem value="expired">{t('photogpt.accounts.status.expired')}</SelectItem>
                        <SelectItem value="banned">{t('photogpt.accounts.status.banned')}</SelectItem>
                    </SelectContent>
                </Select>
                {selectedIds.size > 0 && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBatchDelete}
                        className="h-9 border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-[10px]"
                    >
                        <Trash2 className="mr-2 h-4 w-4" />
                        批量删除 ({selectedIds.size})
                    </Button>
                )}
            </div>

            {/* Table */}
            <div className="rounded-[1.5rem] border border-white/5 bg-card/40 backdrop-blur overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="border-white/5">
                            <TableHead className="w-10">
                                <input
                                    type="checkbox"
                                    className="accent-emerald-500"
                                    checked={selectedIds.size === filteredAccounts.length && filteredAccounts.length > 0}
                                    onChange={toggleSelectAll}
                                />
                            </TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('photogpt.accounts.table.email')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('photogpt.accounts.table.credits')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('photogpt.accounts.table.token')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('photogpt.accounts.table.status')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('photogpt.accounts.table.created')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60 text-right">{t('common.actions')}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">{t('common.loading')}</TableCell>
                            </TableRow>
                        ) : filteredAccounts.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">{t('common.none')}</TableCell>
                            </TableRow>
                        ) : (
                            filteredAccounts.map(account => (
                                <TableRow key={account.id} className="border-white/5 hover:bg-white/[0.02]">
                                    <TableCell className="w-10">
                                        <input
                                            type="checkbox"
                                            className="accent-emerald-500"
                                            checked={selectedIds.has(account.id)}
                                            onChange={() => toggleSelect(account.id)}
                                        />
                                    </TableCell>
                                    <TableCell className="font-medium">{account.email}</TableCell>
                                    <TableCell>
                                        {(() => {
                                            const remaining = Math.max(0, (account.credits ?? 0) - (account.credits_used ?? 0))
                                            const colorClass = remaining <= 0 ? 'text-red-400 border-red-500/30'
                                                : remaining <= 4 ? 'text-amber-400 border-amber-500/30'
                                                : remaining <= 8 ? 'text-yellow-400 border-yellow-500/30'
                                                : 'text-emerald-400 border-emerald-500/30'
                                            return (
                                                <Badge variant="outline" className={`font-mono text-xs border-white/10 ${colorClass}`}>
                                                    {remaining} / {account.credits ?? 0}
                                                </Badge>
                                            )
                                        })()}
                                    </TableCell>
                                    <TableCell>
                                        {account.access_token ? (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-7 text-xs font-mono text-muted-foreground hover:text-foreground"
                                                onClick={() => handleCopy(account.access_token!, account.id)}
                                            >
                                                {copiedId === account.id ? '✅ Copied' : `${account.access_token.slice(0, 20)}...`}
                                            </Button>
                                        ) : (
                                            <span className="text-muted-foreground/40">—</span>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className={cn("text-xs border", statusBadge(account.status))}>
                                            {statusLabel(account.status)}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground text-sm">
                                        {account.created_at ? new Date(account.created_at).toLocaleString() : '—'}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end" className="border-white/10 bg-black/90 backdrop-blur-xl rounded-[10px]">
                                                <DropdownMenuLabel className="text-xs text-muted-foreground">{account.email}</DropdownMenuLabel>
                                                <DropdownMenuSeparator className="bg-white/5" />
                                                <DropdownMenuItem
                                                    className="text-red-400 focus:text-red-400 focus:bg-red-500/10"
                                                    onClick={() => handleDelete(account.id)}
                                                >
                                                    <Trash2 className="mr-2 h-4 w-4" />
                                                    {t('common.delete')}
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
        </div>
    )
}
