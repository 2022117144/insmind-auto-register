import { useEffect, useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import {
    Plus,
    RefreshCw,
    Layers,
    CheckCircle2,
    AlertCircle,
} from 'lucide-react'
import { tasksApi, domainsApi, Task, Domain } from '../services/api'
import { useLanguage } from '../contexts/LanguageContext'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CreateTaskModal } from "@/components/tasks/CreateTaskModal"
import { TaskTable } from "@/components/tasks/TaskTable"

// Module-level caches to prevent UI clear flickering during navigations
let cachedTasks: Task[] = []
let cachedDomains: Domain[] = []

export default function Tasks() {
    const [tasks, setTasks] = useState<Task[]>(cachedTasks)
    const [domains, setDomains] = useState<Domain[]>(cachedDomains)
    const [showModal, setShowModal] = useState(false)
    const [loading, setLoading] = useState(cachedTasks.length === 0)
    const { t } = useLanguage()

    // Removed formData state (moved to Modal)

    const fetchData = async () => {
        try {
            const [tasksData, domainsData] = await Promise.all([
                tasksApi.list(),
                domainsApi.list()
            ])
            cachedTasks = tasksData
            cachedDomains = domainsData.filter(d => d.is_available)
            setTasks(tasksData)
            setDomains(cachedDomains)
        } catch (error) {
            console.error('Failed to fetch data:', error)
        } finally {
            setLoading(false)
        }
    }

    // Initial fetch
    useEffect(() => {
        fetchData()
    }, [])

    // Polling
    usePolling(fetchData, 5000)

    // Removed handleCreate (moved to Modal)

    const handleAction = async (taskId: string, action: 'pause' | 'cancel' | 'delete') => {
        if (action === 'delete' && !confirm(t('common.confirm'))) return // TODO: Use Dialog
        try {
            switch (action) {
                case 'pause': await tasksApi.pause(taskId); break
                case 'cancel': await tasksApi.cancel(taskId); break
                case 'delete': await tasksApi.delete(taskId); break
            }
            fetchData()
        } catch (error) {
            console.error(`Action ${action} failed:`, error)
        }
    }

    const stats = {
        total: tasks.length,
        success: tasks.reduce((sum, t) => sum + t.success_count, 0),
        failed: tasks.reduce((sum, t) => sum + t.failure_count, 0)
    }

    // Removed helper functions (moved to components or constants)

    return (
        <div className="flex-1 space-y-8 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-foreground to-foreground/50 bg-clip-text text-transparent">
                        {t('tasks.title')}
                    </h2>
                    <p className="text-muted-foreground mt-1 text-lg">
                        {t('tasks.subtitle')}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
                        <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                        {t('tasks.sync')}
                    </Button>
                    <Button size="sm" onClick={() => setShowModal(true)}>
                        <Plus className="mr-2 h-4 w-4" />
                        {t('tasks.deploy')}
                    </Button>
                </div>
            </div>

            {/* Stats */}
            <div className="grid gap-4 md:grid-cols-3">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">
                            {t('tasks.total_deployments')}
                        </CardTitle>
                        <Layers className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats.total}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">
                            {t('tasks.confirmed_assets')}
                        </CardTitle>
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-green-500">{stats.success}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">
                            {t('tasks.intercepts')}
                        </CardTitle>
                        <AlertCircle className="h-4 w-4 text-destructive" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-destructive">{stats.failed}</div>
                    </CardContent>
                </Card>
            </div>

            {/* Table */}
            <TaskTable tasks={tasks} onAction={handleAction} />

            {/* Create Task Modal */}
            <CreateTaskModal
                open={showModal}
                onOpenChange={setShowModal}
                domains={domains}
                onSuccess={fetchData}
            />
        </div>
    )
}
