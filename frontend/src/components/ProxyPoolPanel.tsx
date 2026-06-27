import { useEffect, useState } from 'react'
import {
    Activity,
    RefreshCw,
    Server,
    Globe,
    Zap
} from 'lucide-react'
import { proxiesApi } from '../services/api'
import clsx from 'clsx'

interface PoolStatus {
    total: number
    active: number
    idle: number
}

export default function ProxyPoolPanel() {
    const [status, setStatus] = useState<PoolStatus | null>(null)
    const [refreshing, setRefreshing] = useState(false)

    useEffect(() => {
        fetchStatus()
        const interval = setInterval(fetchStatus, 3000)
        return () => clearInterval(interval)
    }, [])

    const fetchStatus = async () => {
        try {
            const data = await proxiesApi.getPoolStatus()
            setStatus(data)
        } catch (error) {
            console.error('Failed to fetch pool status:', error)
        }
    }

    const handleReload = async () => {
        setRefreshing(true)
        try {
            await proxiesApi.reloadPool()
            await fetchStatus()
        } catch (error) {
            console.error('Failed to reload pool:', error)
        } finally {
            setRefreshing(false)
        }
    }

    if (!status) return null

    return (
        <section className="space-y-4">
            <div className="flex items-center gap-3 ml-1">
                <div className="p-2 rounded-xl bg-white/5 border border-white/10">
                    <Server className="w-4 h-4 text-emerald-400" />
                </div>
                <h3 className="text-lg font-black tracking-tight text-white uppercase">LOCAL PROXY POOL</h3>
            </div>

            <div className="card bg-slate-900/10 p-8 border-white/5 space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="p-4 bg-white/5 rounded-xl border border-white/5 flex items-center justify-between">
                        <div>
                            <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">TOTAL NODES</p>
                            <p className="text-2xl font-black text-white mt-1">{status.total}</p>
                        </div>
                        <Globe className="w-8 h-8 text-white/10" />
                    </div>
                    <div className="p-4 bg-emerald-500/10 rounded-xl border border-emerald-500/20 flex items-center justify-between">
                        <div>
                            <p className="text-[10px] font-black text-emerald-500/60 uppercase tracking-widest">ACTIVE</p>
                            <p className="text-2xl font-black text-emerald-400 mt-1">{status.active}</p>
                        </div>
                        <Activity className="w-8 h-8 text-emerald-500/20" />
                    </div>
                    <div className="p-4 bg-blue-500/10 rounded-xl border border-blue-500/20 flex items-center justify-between">
                        <div>
                            <p className="text-[10px] font-black text-blue-500/60 uppercase tracking-widest">IDLE</p>
                            <p className="text-2xl font-black text-blue-400 mt-1">{status.idle}</p>
                        </div>
                        <Zap className="w-8 h-8 text-blue-500/20" />
                    </div>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-white/5">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-xs font-bold text-text-muted uppercase">System Operational</span>
                    </div>
                    <button
                        onClick={handleReload}
                        disabled={refreshing}
                        className="btn-secondary h-9 px-4 text-[10px] font-black gap-2"
                    >
                        <RefreshCw className={clsx("w-3 h-3", refreshing && "animate-spin")} />
                        RELOAD FROM CLASH
                    </button>
                </div>
            </div>
        </section>
    )
}
