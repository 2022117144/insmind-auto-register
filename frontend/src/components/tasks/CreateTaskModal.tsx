
import { useState } from 'react'
import { CheckCircle2 } from 'lucide-react'
import { tasksApi, Domain, CreateTaskData } from '../../services/api'
import { useLanguage } from '../../contexts/LanguageContext'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"

interface CreateTaskModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    domains: Domain[]
    onSuccess: () => void
}

export function CreateTaskModal({ open, onOpenChange, domains, onSuccess }: CreateTaskModalProps) {
    const { t } = useLanguage()
    const [formData, setFormData] = useState<CreateTaskData>({
        total_count: 1,
        domain_mode: 'manual',
        domain_ids: [],
        proxy_strategy: 'round_robin',
        email_prefix_pattern: 'reg_{random6}',
        max_retries: 3,
        email_source: 'cloudflare'
    })

    const handleCreate = async () => {
        if (formData.email_source === 'cloudflare' && (!formData.domain_ids || formData.domain_ids.length === 0)) {
            // alert(t('common.error')) // TODO: Use Toast
            return
        }
        try {
            await tasksApi.create(formData)
            onOpenChange(false)
            onSuccess()
        } catch (error) {
            console.error('Failed to create task:', error)
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[480px] bg-[#111214] border-white/5 border-t-white/10 shadow-2xl rounded-2xl p-0 overflow-hidden gap-0">
                <DialogHeader className="p-6 pb-2">
                    <DialogTitle className="text-xl font-bold tracking-tight">新建任务</DialogTitle>
                    <DialogDescription className="text-muted-foreground/50 text-xs">
                        配置注册自动化参数，开始批量任务
                    </DialogDescription>
                </DialogHeader>
                <div className="px-6 py-4 space-y-5">
                    <div className="space-y-2">
                        <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 ml-0.5">
                            {t('tasks.modal.nodes')}
                        </label>
                        <Input
                            id="total_count"
                            type="number"
                            className="h-11 bg-white/[0.03] border-white/5 focus-visible:ring-primary focus-visible:border-primary/50 transition-all rounded-xl"
                            value={formData.total_count}
                            onChange={e => setFormData({ ...formData, total_count: Number(e.target.value) })}
                            min={1} max={500}
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 ml-0.5">
                            {t('tasks.modal.strategy')}
                        </label>
                        <Select
                            value={formData.proxy_strategy}
                            onValueChange={(val) => setFormData({ ...formData, proxy_strategy: val as any })}
                        >
                            <SelectTrigger className="h-11 bg-white/[0.03] border-white/5 focus:ring-primary focus:border-primary/50 transition-all rounded-xl">
                                <SelectValue placeholder="Select strategy" />
                            </SelectTrigger>
                            <SelectContent className="bg-card border-white/10 rounded-xl overflow-hidden shadow-2xl">
                                <SelectItem value="round_robin" className="focus:bg-primary/10 hover:bg-primary/10 py-3">轮询 (Round Robin)</SelectItem>
                                <SelectItem value="random" className="focus:bg-primary/10 hover:bg-primary/10 py-3">随机 (Stochastic)</SelectItem>
                                <SelectItem value="least_used" className="focus:bg-primary/10 hover:bg-primary/10 py-3">最优路径 (Optimal Path)</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 ml-0.5">
                            最大重试次数
                        </label>
                        <Input
                            id="max_retries"
                            type="number"
                            className="h-11 bg-white/[0.03] border-white/5 focus-visible:ring-primary focus-visible:border-primary/50 transition-all rounded-xl"
                            value={formData.max_retries}
                            onChange={e => setFormData({ ...formData, max_retries: Number(e.target.value) })}
                            min={0} max={10}
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 ml-0.5">
                            邮箱来源
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                            <Button
                                type="button"
                                variant={formData.email_source === 'cloudflare' ? 'default' : 'outline'}
                                className="h-11 rounded-xl"
                                onClick={() => setFormData({ ...formData, email_source: 'cloudflare' })}
                            >
                                Cloudflare 域名
                            </Button>
                            <Button
                                type="button"
                                variant={formData.email_source === 'outlook' ? 'default' : 'outline'}
                                className="h-11 rounded-xl"
                                onClick={() => setFormData({ ...formData, email_source: 'outlook' })}
                            >
                                Outlook 邮箱池
                            </Button>
                        </div>
                    </div>

                    {formData.email_source === 'cloudflare' ? (
                        <>
                            <div className="space-y-2">
                                <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 ml-0.5">
                                    {t('tasks.modal.realms')}
                                </label>
                                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                                    <ScrollArea className="h-[120px] w-full">
                                        <div className="space-y-1.5 pr-4">
                                            {domains.map(domain => (
                                                <div key={domain.id} className="group relative flex items-center space-x-3 p-2 rounded-lg hover:bg-white/[0.02] transition-all cursor-pointer"
                                                    onClick={() => {
                                                        const currentIds = formData.domain_ids || [];
                                                        const newIds = currentIds.includes(domain.id)
                                                            ? currentIds.filter(id => id !== domain.id)
                                                            : [...currentIds, domain.id];
                                                        setFormData({ ...formData, domain_ids: newIds });
                                                    }}
                                                >
                                                    <div className={cn(
                                                        "flex h-4 w-4 items-center justify-center rounded border transition-all",
                                                        (formData.domain_ids || []).includes(domain.id)
                                                            ? "bg-primary border-primary"
                                                            : "bg-white/5 border-white/10 group-hover:border-white/20"
                                                    )}>
                                                        {(formData.domain_ids || []).includes(domain.id) && <CheckCircle2 className="h-3 w-3 text-background" />}
                                                    </div>
                                                    <label className="text-sm font-medium leading-none cursor-pointer flex-1">
                                                        {domain.domain}
                                                    </label>
                                                    <Badge variant="outline" className="text-[9px] opacity-20 group-hover:opacity-40 transition-opacity">
                                                        可用
                                                    </Badge>
                                                </div>
                                            ))}
                                        </div>
                                    </ScrollArea>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 ml-0.5">
                                    {t('tasks.modal.pattern')}
                                </label>
                                <div className="space-y-3">
                                    <Input
                                        value={formData.email_prefix_pattern}
                                        onChange={e => setFormData({ ...formData, email_prefix_pattern: e.target.value })}
                                        className="h-11 bg-white/[0.05] border-white/10 focus-visible:ring-primary font-mono text-sm rounded-xl"
                                    />
                                    <div className="flex flex-wrap gap-1.5">
                                        {['{random6}', '{random8}', '{letter6}', '{digit6}', '{timestamp}'].map(tag => (
                                            <Badge
                                                key={tag}
                                                variant="secondary"
                                                className="px-2.5 py-1 text-[10px] bg-white/[0.03] border-white/5 hover:bg-white/[0.08] hover:border-white/10 transition-all cursor-pointer font-mono"
                                                onClick={() => setFormData({ ...formData, email_prefix_pattern: formData.email_prefix_pattern + tag })}
                                            >
                                                {tag}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 text-center">
                            <p className="text-sm text-muted-foreground">
                                将自动从 Outlook 邮箱池中分配可用邮箱进行注册。并免去自动配置前缀的过程。
                            </p>
                            <p className="text-xs text-muted-foreground opacity-50 mt-1">请确保已经在 Outlook 邮箱池导入了充足的邮箱账号</p>
                        </div>
                    )}
                </div>
                <DialogFooter className="p-6 bg-white/[0.02] border-t border-white/5 flex gap-3">
                    <Button
                        variant="ghost"
                        className="flex-1 h-11 rounded-xl text-muted-foreground hover:bg-white/5 hover:text-foreground"
                        onClick={() => onOpenChange(false)}
                    >
                        {t('common.abort')}
                    </Button>
                    <Button
                        className="flex-1 h-11 rounded-xl bg-foreground text-background font-bold hover:bg-foreground/90 transition-all shadow-lg shadow-black/20"
                        onClick={handleCreate}
                    >
                        {t('common.execute')}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
