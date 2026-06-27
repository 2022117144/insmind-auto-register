请审查以下前端 TypeScript/TSX 文件。

项目背景: insMind (稿定设计海外版) 自动注册系统前端
文件路径: frontend/src/pages/InsMindAccounts.tsx
文件类型: accounts

审查重点：
- routes/translations 文件：检查路由配置、导入路径、翻译键是否完整
- 页面组件文件：检查 API 对接、UI 一致性、错误处理、状态管理
- 确认无遗留 Dreamina 名称 (jimeng、dreamina 等)

文件内容:
```typescript
import { useEffect, useState } from 'react'
import {
    Trash2,
    MoreHorizontal,
    Search,
    RefreshCw
} from 'lucide-react'
import { toast } from 'sonner'
import { insmindAccountsApi, InsMindAccount } from '../services/api'
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
let cachedAccounts: InsMindAccount[] = []
let cachedFilterStatus = 'all'

export default function InsMindAccounts() {
    const [accounts, setAccounts] = useState<InsMindAccount[]>(cachedAccounts)
    const [loading, setLoading] = useState(cachedAccounts.length === 0)
    const [searchQuery, setSearchQuery] = useState('')
    const [filterStatus, setFilterStatus] = useState(cachedFilterStatus)
    const [copiedId, setCopiedId] = useState<number | null>(null)
    const { t } = useLanguage()

    useEffect(() => {
        fetchAccounts()
    }, [filterStatus])

    const fetchAccounts = async () => {
        setLoading(true)
        try {
            const data = await insmindAccountsApi.list({
                status: filterStatus !== 'all' ? filterStatus : undefined,
            })
            cachedAccounts = data
            setAccounts(data)
        } catch (error) {
            toast.error('获取 insMind 账号失败')
            console.error(error)
        } finally {
            setLoading(false)
        }
    }

    const handleDelete = async (id: number) => {
        if (!confirm(t('common.confirm_delete'))) return
        try {
            await insmindAccountsApi.delete(id)
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
            active: t('insmind.accounts.status.active'),
            expired: t('insmind.accounts.status.expired'),
            banned: t('insmind.accounts.status.banned'),
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
                    <h2 className="text-3xl font-bold tracking-tight">{t('insmind.accounts.title')}</h2>
                    <p className="text-muted-foreground">{t('insmind.accounts.subtitle')}</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={fetchAccounts} disabled={loading} className="h-9 border-white/5 bg-card/40 rounded-[10px]">
                        <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />
                        {t('common.sync')}
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: '全部', value: accounts.length, color: 'text-sky-400' },
                    { label: t('insmind.accounts.status.active'), value: accounts.filter(a => a.status === 'active').length, color: 'text-emerald-400' },
                    { label: t('insmind.accounts.status.expired'), value: accounts.filter(a => a.status === 'expired').length, color: 'text-amber-400' },
                    { label: t('insmind.accounts.status.banned'), value: accounts.filter(a => a.status === 'banned').length, color: 'text-red-400' },
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
                        <SelectItem value="active">{t('insmind.accounts.status.active')}</SelectItem>
                        <SelectItem value="expired">{t('insmind.accounts.status.expired')}</SelectItem>
                        <SelectItem value="banned">{t('insmind.accounts.status.banned')}</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Table */}
            <div className="rounded-[1.5rem] border border-white/5 bg-card/40 backdrop-blur overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="border-white/5">
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('insmind.accounts.table.email')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('insmind.accounts.table.credits')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('insmind.accounts.table.token')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('insmind.accounts.table.status')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">{t('insmind.accounts.table.created')}</TableHead>
                            <TableHead className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60 text-right">{t('common.actions')}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">{t('common.loading')}</TableCell>
                            </TableRow>
                        ) : filteredAccounts.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">{t('common.none')}</TableCell>
                            </TableRow>
                        ) : (
                            filteredAccounts.map(account => (
                                <TableRow key={account.id} className="border-white/5 hover:bg-white/[0.02]">
                                    <TableCell className="font-medium">{account.email}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="font-mono text-xs border-white/10">
                                            {account.credits ?? 0}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        {account.token ? (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-7 text-xs font-mono text-muted-foreground hover:text-foreground"
                                                onClick={() => handleCopy(account.token!, account.id)}
                                            >
                                                {copiedId === account.id ? '✅ Copied' : `${account.token.slice(0, 20)}...`}
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
```

请按以下格式输出：
## 审查结果
- 功能正确性: PASS/FAIL | 理由
- UI/UX 一致性: PASS/FAIL | 理由
- 代码质量: PASS/FAIL | 理由
- 安全性: PASS/FAIL | 理由
- 完整性: PASS/FAIL | 理由

## 具体问题
列出所有发现的问题（如果有）

## 改进建议
