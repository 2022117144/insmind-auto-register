import { useEffect, useState, useRef } from 'react'
import {
    Trash2,
    Download,
    Wifi,
    WifiOff,
    Terminal
} from 'lucide-react'
import { useLanguage } from '../contexts/LanguageContext'
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Card } from "@/components/ui/card"


interface LogEntry {
    type: string
    timestamp: string
    level: string
    message: string
    email?: string
    task_id?: string
}

export default function Logs() {
    const [logs, setLogs] = useState<LogEntry[]>([])
    const [levelFilter, setLevelFilter] = useState<string>('all')
    const [connected, setConnected] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)
    const wsRef = useRef<WebSocket | null>(null)
    const { t } = useLanguage()

    useEffect(() => {
        connectWebSocket()
        return () => {
            if (wsRef.current) wsRef.current.close()
        }
    }, [])

    useEffect(() => {
        // Auto-scroll to bottom
        const scrollViewport = containerRef.current?.querySelector('[data-radix-scroll-area-viewport]');
        if (scrollViewport) {
            scrollViewport.scrollTop = scrollViewport.scrollHeight;
        }
    }, [logs]);


    const connectWebSocket = () => {
        const ws = new WebSocket('ws://localhost:8005/ws/logs')

        ws.onopen = () => {
            setConnected(true)
            console.log('WebSocket connected')
        }

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                if (data.type === 'log') {
                    setLogs(prev => [...prev.slice(-500), data])
                }
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e)
            }
        }

        ws.onclose = () => {
            setConnected(false)
            setTimeout(connectWebSocket, 5000)
        }

        ws.onerror = () => setConnected(false)
        wsRef.current = ws
    }

    const clearLogs = () => setLogs([])



    const filteredLogs = levelFilter !== 'all'
        ? logs.filter(log => log.level.toUpperCase() === levelFilter)
        : logs

    return (
        <div className="space-y-6 h-[calc(100vh-8rem)] flex flex-col">
            <div className="flex items-center justify-between shrink-0">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">{t('logs.title')}</h2>
                    <div className="flex items-center gap-2 mt-1">
                        <p className="text-muted-foreground">{t('logs.subtitle')}</p>
                        <Badge variant={connected ? "default" : "destructive"} className="ml-2">
                            {connected ? <Wifi className="h-3 w-3 mr-1" /> : <WifiOff className="h-3 w-3 mr-1" />}
                            {connected ? t('logs.status.connected') : t('logs.status.disconnected')}
                        </Badge>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-[150px]">
                        <Select value={levelFilter} onValueChange={setLevelFilter}>
                            <SelectTrigger>
                                <SelectValue placeholder={t('logs.filter.level')} />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">{t('logs.filter.all')}</SelectItem>
                                <SelectItem value="INFO">INFO</SelectItem>
                                <SelectItem value="WARNING">WARNING</SelectItem>
                                <SelectItem value="ERROR">ERROR</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <Button variant="outline" onClick={clearLogs}>
                        <Trash2 className="mr-2 h-4 w-4" />
                        {t('logs.purge')}
                    </Button>
                    <Button variant="ghost" disabled>
                        <Download className="mr-2 h-4 w-4" />
                        {t('common.export')}
                    </Button>
                </div>
            </div>

            <Card className="flex-1 overflow-hidden bg-slate-950 text-slate-50 font-mono text-sm border-slate-800 relative flex flex-col">
                <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-900/50">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <Terminal className="h-4 w-4" />
                        <span>{t('logs.console')}</span>
                    </div>
                    <div className="text-xs text-slate-500">
                        {filteredLogs.length} {t('logs.lines')}
                    </div>
                </div>

                <ScrollArea className="flex-1 p-4" ref={containerRef}>
                    <div className="space-y-1">
                        {filteredLogs.map((log, index) => (
                            <div key={index} className="flex gap-4 hover:bg-white/5 p-1 rounded">
                                <span className="text-slate-500 shrink-0 text-xs text-[10px] mt-0.5 select-none">
                                    {new Date(log.timestamp).toLocaleTimeString()}
                                </span>
                                <div className={`shrink-0 w-16 text-xs font-bold ${log.level === 'ERROR' ? 'text-red-400' :
                                    log.level === 'WARNING' ? 'text-yellow-400' :
                                        'text-blue-400'
                                    }`}>
                                    [{log.level}]
                                </div>
                                <div className="break-all flex-1 text-slate-300">
                                    {log.message}
                                    {log.email && <span className="ml-2 text-slate-500">({log.email})</span>}
                                    {log.task_id && <span className="ml-2 text-slate-600">[Task: {log.task_id.substring(0, 6)}]</span>}
                                </div>
                            </div>
                        ))}
                        {/* Fake cursor at the end */}
                        <div className="h-4 w-2 bg-slate-500 animate-pulse mt-1" />
                    </div>
                </ScrollArea>
            </Card>
        </div>
    )
}
