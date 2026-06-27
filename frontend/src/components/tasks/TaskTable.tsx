
import {
    Pause,
    StopCircle,
    Trash2,
} from 'lucide-react'
import { Task } from '../../services/api'
import { useLanguage } from '../../contexts/LanguageContext'
import { Button } from "@/components/ui/button"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { parseRegion } from "@/lib/constants"

interface TaskTableProps {
    tasks: Task[]
    onAction: (taskId: string, action: 'pause' | 'cancel' | 'delete') => void
}

export function TaskTable({ tasks, onAction }: TaskTableProps) {
    const { t } = useLanguage()

    const getProgressDisplay = (task: Task) => {
        const isFailed = task.status === 'failed';
        const isRunning = task.status === 'running';
        const isSuccess = task.status === 'completed';
        const isPaused = task.status === 'paused';

        const colorClass = isFailed ? "bg-destructive" : isSuccess ? "bg-emerald-500" : isRunning ? "bg-primary" : "bg-muted-foreground/30";
        const textClass = isFailed ? "text-destructive" : isSuccess ? "text-emerald-500 font-bold" : isRunning ? "text-primary font-bold" : "text-muted-foreground";

        return (
            <div className="w-[120px] space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-[11px] px-0.5">
                    <span className={`uppercase tracking-wider ${textClass}`}>
                        {isFailed ? "Failed" : isSuccess ? "Success" : isPaused ? "Paused" : isRunning ? "Running" : "Created"}
                    </span>
                    <span className="font-mono font-medium text-muted-foreground/80">
                        {Math.round(task.progress || 0)}%
                    </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-secondary/50 overflow-hidden">
                    <div
                        className={`h-full transition-all duration-500 ease-out ${colorClass}`}
                        style={{ width: `${task.progress || 0}%` }}
                    />
                </div>
            </div>
        )
    }

    const getProxyRegionDisplay = (task: Task) => {
        const region = parseRegion(task.assigned_proxy_region)
        if (!region) return <span className="text-muted-foreground text-xs">--</span>
        return (
            <div className="flex items-center gap-2">
                <img
                    src={region.flag}
                    alt={region.name}
                    className="w-4 h-3 object-cover rounded shadow-sm"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
                <span className="text-xs font-medium">{region.name}</span>
            </div>
        )
    }

    return (
        <div className="bg-card/20 rounded-xl border border-border/30 overflow-hidden">
            <Table>
                <TableHeader className="bg-muted/10">
                    <TableRow className="hover:bg-transparent border-border/20">
                        <TableHead className="w-[100px] text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 py-4">{t('tasks.table.id')}</TableHead>
                        <TableHead className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 py-4">{t('tasks.table.target')}</TableHead>
                        <TableHead className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 py-4">{t('tasks.table.proxy')}</TableHead>
                        <TableHead className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 py-4">{t('tasks.table.status')}</TableHead>
                        <TableHead className="text-right text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 py-4">Attempts</TableHead>
                        <TableHead className="text-right text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 py-4">{t('tasks.table.created')}</TableHead>
                        <TableHead className="text-right text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 py-4">{t('common.actions')}</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {tasks.length === 0 ? (
                        <TableRow>
                            <TableCell colSpan={7} className="h-24 text-center">
                                {t('common.none')}
                            </TableCell>
                        </TableRow>
                    ) : (
                        tasks.map((task) => (
                            <TableRow key={task.task_id}>
                                <TableCell className="font-medium">#{task.task_id.slice(0, 8)}</TableCell>
                                <TableCell>{task.assigned_email || <span className="text-muted-foreground italic">Unassigned</span>}</TableCell>
                                <TableCell>{getProxyRegionDisplay(task)}</TableCell>
                                <TableCell>{getProgressDisplay(task)}</TableCell>
                                <TableCell className="text-right font-mono text-xs">
                                    {task.status === 'created' ? '-' :
                                        `${(task.retry_count || 0) + 1} / ${task.max_retries || 3}`}
                                </TableCell>
                                <TableCell className="text-right">{new Date(task.created_at).toLocaleString('zh-CN', { hour12: false })}</TableCell>
                                <TableCell className="text-right">
                                    <div className="flex justify-end gap-2">
                                        {task.status === 'running' && (
                                            <Button variant="ghost" size="icon" onClick={() => onAction(task.task_id, 'pause')}>
                                                <Pause className="h-4 w-4" />
                                            </Button>
                                        )}
                                        {task.status !== 'completed' && task.status !== 'cancelled' && (
                                            <Button variant="ghost" size="icon" onClick={() => onAction(task.task_id, 'cancel')}>
                                                <StopCircle className="h-4 w-4 text-destructive" />
                                            </Button>
                                        )}
                                        <Button variant="ghost" size="icon" onClick={() => onAction(task.task_id, 'delete')} disabled={task.status === 'running'}>
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ))
                    )}
                </TableBody>
            </Table>
        </div>
    )
}
