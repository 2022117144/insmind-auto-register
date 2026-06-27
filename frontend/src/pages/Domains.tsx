import { useEffect, useState } from 'react'
import {
    Plus,
    Trash2,
    TestTube,
    Globe,
    Cloud
} from 'lucide-react'
import { toast } from 'sonner'
import { domainsApi, Domain, CreateDomainData } from '../services/api'
import { cn } from "@/lib/utils"
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
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"


// Module-level caches to prevent UI clear flickering during navigations
let cachedDomains: Domain[] = []

export default function Domains() {
    const [domains, setDomains] = useState<Domain[]>(cachedDomains)
    const [showModal, setShowModal] = useState(false)
    const [testing, setTesting] = useState<number | null>(null)
    const { t } = useLanguage()

    const [formData, setFormData] = useState<CreateDomainData>({
        domain: '',
        cf_zone_id: '',
        usage_limit: 0,
        note: ''
    })

    useEffect(() => {
        const fetchDomains = async () => {
            try {
                const data = await domainsApi.list()
                cachedDomains = data
                setDomains(data)
            } catch (error) {
                console.error('Failed to fetch domains:', error)
            }
        }
        fetchDomains()
    }, [])

    const handleCreate = async () => {
        if (!formData.domain) {
            toast.error('Domain name is required')
            return
        }
        try {
            await domainsApi.create(formData)
            toast.success('Domain added successfully')
            setShowModal(false)
            setFormData({ domain: '', cf_zone_id: '', usage_limit: 0, note: '' })
            // Re-fetch domains after creation
            const data = await domainsApi.list()
            cachedDomains = data
            setDomains(data)
        } catch (error: any) {
            toast.error(error.message || 'Failed to add domain')
        }
    }

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this domain?')) return
        try {
            await domainsApi.delete(id)
            toast.success('Domain deleted')
            // Re-fetch domains after deletion
            const data = await domainsApi.list()
            cachedDomains = data
            setDomains(data)
        } catch (error: any) {
            toast.error(error.message || 'Delete failed')
        }
    }

    const handleToggle = async (id: number) => {
        try {
            await domainsApi.toggle(id)
            // Re-fetch domains after toggle
            const data = await domainsApi.list()
            cachedDomains = data
            setDomains(data)
        } catch (error: any) {
            toast.error(error.message || 'Toggle failed')
        }
    }

    const handleTest = async (id: number) => {
        setTesting(id)
        try {
            const result = await domainsApi.test(id)
            toast.success(result.message)
        } catch (error: any) {
            toast.error(error.message || 'Test failed')
        } finally {
            setTesting(null)
        }
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div className="space-y-1">
                    <h1 className="text-2xl font-bold tracking-tight">{t('domains.title')}</h1>
                    <p className="text-muted-foreground text-sm">
                        {t('domains.subtitle')}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <Button
                        size="sm"
                        onClick={() => setShowModal(true)}
                        className="shadow-lg shadow-primary/20"
                    >
                        <Plus className="mr-2 h-4 w-4" />
                        {t('domains.add')}
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="bg-card/30 border-border/50 overflow-hidden group hover:border-primary/20 transition-all">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground/50 flex items-center gap-2">
                            <Globe className="h-4 w-4 text-primary" />
                            {t('domains.total')}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{domains.length}</div>
                    </CardContent>
                </Card>

                <Card className="bg-card/30 border-border/50 overflow-hidden group hover:border-primary/20 transition-all">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground/50 flex items-center gap-2">
                            <Cloud className="h-4 w-4 text-green-500" />
                            {t('domains.active')}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {domains.filter(d => d.is_enabled).length}
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-card/30 border-border/50 overflow-hidden group hover:border-primary/20 transition-all">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground/50 flex items-center gap-2">
                            <Plus className="h-4 w-4 text-amber-500" />
                            {t('domains.usage')}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono">
                            {domains.reduce((acc, d) => acc + (d.usage_count || 0), 0)}
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Card className="border-none shadow-2xl bg-card/30 backdrop-blur-sm overflow-hidden rounded-2xl">
                <Table>
                    <TableHeader className="bg-secondary/50">
                        <TableRow className="hover:bg-transparent border-border/50">
                            <TableHead className="w-[12px]"></TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50">{t('domains.table.realm')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50">{t('domains.table.pointer')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50">{t('domains.table.load')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50">{t('domains.table.integrity')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50">{t('common.status')}</TableHead>
                            <TableHead className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 text-right">{t('common.actions')}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {domains.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={7} className="h-64 text-center">
                                    <div className="flex flex-col items-center gap-2 text-muted-foreground">
                                        <Globe className="h-12 w-12 opacity-10" />
                                        <p className="text-lg font-medium tracking-tight animate-pulse">No domains configured yet</p>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ) : (
                            domains.map(domain => (
                                <TableRow key={domain.id} className="group hover:bg-secondary/30 transition-colors">
                                    <TableCell className="px-6">
                                        <Switch
                                            checked={domain.is_enabled}
                                            onCheckedChange={() => handleToggle(domain.id)}
                                            className="scale-110"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex flex-col gap-0.5 py-1">
                                            <div className="flex items-center gap-2">
                                                <Globe className="h-4 w-4 text-primary opacity-70 group-hover:opacity-100 transition-opacity" />
                                                <span className="font-bold tracking-tight text-base">{domain.domain}</span>
                                            </div>
                                            <span className="text-xs text-muted-foreground/70 pl-6 italic">{domain.note || 'Internal endpoint'}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="secondary" className="font-mono text-[10px] py-1 px-3 bg-secondary/50 rounded-lg">
                                            {domain.cf_zone_id || 'N/A'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <div className="flex flex-col items-center gap-1.5 min-w-[120px]">
                                            <div className="flex justify-between w-full text-[11px] font-bold text-muted-foreground px-1">
                                                <span>{domain.usage_count} units</span>
                                                <span>{domain.usage_limit || '∞'}</span>
                                            </div>
                                            <div className="w-full h-1.5 bg-secondary/80 rounded-full overflow-hidden border border-border/10">
                                                <div
                                                    className={cn("h-full transition-all duration-1000 bg-primary shadow-[0_0_8px_rgba(var(--primary),0.5)]",
                                                        domain.usage_limit > 0 && (domain.usage_count / domain.usage_limit) > 0.8 ? "bg-orange-500" : ""
                                                    )}
                                                    style={{ width: `${domain.usage_limit > 0 ? Math.min(100, (domain.usage_count / domain.usage_limit) * 100) : 100}%` }}
                                                />
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <Badge
                                            variant={domain.is_available ? "default" : "destructive"}
                                            className={cn("px-3 py-1 text-[10px] font-black tracking-widest",
                                                domain.is_available ? "bg-green-500/10 text-green-500 border-green-500/20" : ""
                                            )}
                                        >
                                            {domain.is_available ? 'OPERATIONAL' : 'ERROR'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <Badge
                                            variant={domain.is_enabled ? "default" : "secondary"}
                                            className={cn("px-3 py-1 text-[10px] font-black tracking-widest",
                                                domain.is_enabled ? "bg-blue-500/10 text-blue-500 border-blue-500/20" : ""
                                            )}
                                        >
                                            {domain.is_enabled ? 'ACTIVE' : 'INACTIVE'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right px-6">
                                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <Button variant="ghost" size="icon" onClick={() => handleTest(domain.id)} disabled={testing === domain.id} className="rounded-full hover:bg-primary/10 hover:text-primary">
                                                <TestTube className={cn("h-4 w-4", testing === domain.id && "animate-spin")} />
                                            </Button>
                                            <Button variant="ghost" size="icon" onClick={() => handleDelete(domain.id)} className="rounded-full hover:bg-destructive/10 hover:text-destructive">
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </Card>

            <Dialog open={showModal} onOpenChange={setShowModal}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t('domains.modal.title')}</DialogTitle>
                        <DialogDescription>
                            {t('domains.modal.desc')}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="domain">{t('domains.modal.name')}</Label>
                            <Input
                                id="domain"
                                placeholder="example.com"
                                value={formData.domain}
                                onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="zone_id">{t('domains.modal.zone_id')}</Label>
                            <Input
                                id="zone_id"
                                placeholder="..."
                                value={formData.cf_zone_id}
                                onChange={(e) => setFormData({ ...formData, cf_zone_id: e.target.value })}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="limit">{t('domains.modal.limit')}</Label>
                            <Input
                                id="limit"
                                type="number"
                                value={formData.usage_limit}
                                onChange={(e) => setFormData({ ...formData, usage_limit: parseInt(e.target.value) })}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="note">{t('domains.modal.note')}</Label>
                            <Input
                                id="note"
                                placeholder="..."
                                value={formData.note}
                                onChange={(e) => setFormData({ ...formData, note: e.target.value })}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
                        <Button onClick={handleCreate}>Confirm Add</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
