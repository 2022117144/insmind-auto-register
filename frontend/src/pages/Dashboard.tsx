import { useEffect, useState } from 'react'
import {
    Users,
    CheckCircle,
    Activity,
    RefreshCw,
    Zap,
    ShieldCheck,
    Cloud,
    FileJson,
    History as HistoryIcon
} from 'lucide-react'
import { api } from '../services/api'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useLanguage } from '@/contexts/LanguageContext'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

interface DashboardStats {
    accounts: {
        total: number
        success: number
        failed: number
        success_rate: number
        today_success: number
    }
    proxies: {
        total: number
        active: number
        online_ratio: string
    }
    trends: {
        name: string
        total: number
    }[]
}

interface HealthStatus {
    clash: string
    cloudflare_kv: string
}

const Dashboard = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null)
    const [health, setHealth] = useState<HealthStatus | null>(null)
    const [loading, setLoading] = useState(true)
    const { t } = useLanguage()

    const fetchData = async () => {
        setLoading(true)
        try {
            const [statsRes, healthRes] = await Promise.all([
                api.get<DashboardStats>('/dashboard/stats'),
                api.get<{ services: HealthStatus }>('/health')
            ])
            setStats(statsRes)
            setHealth(healthRes.services)
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
    }, [])

    const projectStats = [
        { label: t('dashboard.total_accounts'), value: stats?.accounts.total ?? 0, description: t('dashboard.total_accounts_desc'), icon: Users, color: "text-sky-400" },
        { label: t('dashboard.success_rate'), value: `${stats?.accounts.success_rate ?? 0}%`, description: t('dashboard.success_rate_desc'), icon: Activity, color: "text-emerald-400" },
        { label: t('nav.proxies'), value: stats?.proxies.online_ratio ?? "0/0", description: t('proxies.subtitle'), icon: ShieldCheck, color: "text-amber-400" },
        { label: t('dashboard.today_success'), value: stats?.accounts.today_success ?? 0, description: t('dashboard.today_success_desc'), icon: CheckCircle, color: "text-emerald-500" },
    ];

    if (loading) return <div className="p-8 text-muted-foreground font-bold animate-pulse">{t('common.loading')}</div>

    return (
        <div className="flex-1 space-y-10 pt-6 animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-foreground to-foreground/50 bg-clip-text text-transparent">{t('dashboard.title')}</h2>
                    <p className="text-muted-foreground mt-1 text-lg">{t('dashboard.subtitle')}</p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" size="lg" onClick={fetchData} className="bg-card/40 border-border/40 text-xs font-bold h-11 rounded-xl hover:bg-card/60 transition-all shadow-sm">
                        <RefreshCw className="mr-2 h-4 w-4 opacity-40" />
                        {t('common.refresh')}
                    </Button>
                    <Button asChild size="lg" className="bg-foreground text-background hover:bg-foreground/90 font-bold text-xs h-11 rounded-xl px-6 shadow-xl shadow-white/5 transition-all">
                        <Link to="/tasks">
                            <Zap className="mr-2 h-4 w-4 fill-current" />
                            {t('dashboard.deploy_task')}
                        </Link>
                    </Button>
                </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                {projectStats.map((stat) => (
                    <Card key={stat.label} className="border-none bg-card/40 hover:bg-card/60 transition-all rounded-2xl overflow-hidden group shadow-lg backdrop-blur-sm">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-[11px] font-black text-muted-foreground/40 uppercase tracking-[0.2em]">
                                {stat.label}
                            </CardTitle>
                            <div className={cn("p-2 rounded-lg bg-background/50 border border-border/10", stat.color.replace('text-', 'bg-').replace('400', '400/10').replace('500', '500/10'))}>
                                <stat.icon className={cn("h-4 w-4 opacity-80 group-hover:opacity-100 transition-opacity", stat.color)} />
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="text-4xl font-black tracking-tighter mb-2">{stat.value}</div>
                            <p className="text-[11px] text-muted-foreground/30 font-bold italic">{stat.description}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-7 pb-10">
                <Card className="col-span-4 border-none bg-card/20 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-md">
                    <CardHeader className="flex flex-row items-center justify-between pb-8 pt-8 px-8">
                        <div>
                            <CardTitle className="text-lg font-black text-sky-400 tracking-tight uppercase">注册趋势</CardTitle>
                            <CardDescription className="text-xs text-muted-foreground/40 font-bold">近 7 日注册量走势统计图表</CardDescription>
                        </div>
                    </CardHeader>
                    <CardContent className="px-2 pb-8">
                        <div className="h-[350px] w-full mt-4">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={stats?.trends || []} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--sky))" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="hsl(var(--sky))" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                                    <XAxis dataKey="name" axisLine={false} tickLine={false} className="text-[10px] font-bold text-muted-foreground/30" dy={15} />
                                    <YAxis axisLine={false} tickLine={false} className="text-[10px] font-bold text-muted-foreground/30" dx={-10} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#0a0c10', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px', fontSize: '11px', fontWeight: '800', backdropFilter: 'blur(10px)', boxShadow: '0 20px 50px rgba(0,0,0,0.5)' }}
                                        cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }}
                                    />
                                    <Area type="monotone" dataKey="total" stroke="hsl(var(--sky))" strokeWidth={3} fillOpacity={1} fill="url(#colorTotal)" animationDuration={2000} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>

                <Card className="col-span-3 border-none bg-card/20 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-md">
                    <CardHeader className="pb-8 pt-8 px-8">
                        <CardTitle className="text-lg font-black text-emerald-400 tracking-tight uppercase">服务状态</CardTitle>
                        <CardDescription className="text-xs text-muted-foreground/40 font-bold">关键后台基础设施健康检查。</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4 px-8 pb-8">
                        <div className="grid gap-3">
                            {[
                                { name: 'Clash 代理服务器', status: health?.clash === 'connected' ? '就绪' : '连接中', desc: '确保注册请求链路加密', icon: ShieldCheck, color: health?.clash === 'connected' ? 'text-emerald-500' : 'text-amber-500' },
                                { name: '数据存储中心', status: health?.cloudflare_kv === 'configured' ? '正常' : '异常', desc: '账号与配置实时同步', icon: Cloud, color: health?.cloudflare_kv === 'configured' ? 'text-emerald-500' : 'text-rose-500' }
                            ].map((service) => (
                                <div key={service.name} className="flex items-center p-4 rounded-xl bg-muted/10 border border-border/10 group hover:border-border/40 transition-all">
                                    <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg bg-background/60 border border-border/20 shadow-inner", service.color)}>
                                        <service.icon className="h-5 w-5 opacity-90" />
                                    </div>
                                    <div className="ml-4">
                                        <p className="text-sm font-bold tracking-tight">{service.name}</p>
                                        <p className="text-[10px] text-muted-foreground/40 font-medium">{service.desc}</p>
                                    </div>
                                    <div className="ml-auto">
                                        <Badge variant="outline" className={cn("px-2 py-0.5 h-6 rounded-md text-[9px] font-black uppercase tracking-wider border-none", service.status === '就绪' || service.status === '正常' ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-500")}>
                                            <div className="flex items-center">
                                                <div className={cn("h-1.5 w-1.5 rounded-full mr-2", service.status === '就绪' || service.status === '正常' ? "bg-emerald-500 animate-pulse" : "bg-amber-500")} />
                                                {service.status}
                                            </div>
                                        </Badge>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="pt-6 grid grid-cols-2 gap-3">
                            <Button variant="secondary" size="sm" className="bg-muted/20 border border-border/10 font-bold text-[11px] h-10 rounded-xl text-muted-foreground hover:text-foreground transition-all shadow-sm" asChild>
                                <Link to="/accounts">
                                    <FileJson className="mr-2 h-4 w-4 opacity-40" />
                                    原始数据
                                </Link>
                            </Button>
                            <Button variant="secondary" size="sm" className="bg-muted/20 border border-border/10 font-bold text-[11px] h-10 rounded-xl text-muted-foreground hover:text-foreground transition-all shadow-sm" asChild>
                                <Link to="/logs">
                                    <HistoryIcon className="mr-2 h-4 w-4 opacity-40" />
                                    运行日志
                                </Link>
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

export default Dashboard;
