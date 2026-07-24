/**
 * API 客户端
 */

const BASE_URL = '/api'

interface ApiOptions {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
    body?: unknown
}

async function request<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
    const { method = 'GET', body } = options

    const config: RequestInit = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    }

    if (body) {
        config.body = JSON.stringify(body)
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, config)

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
}

export const api = {
    get: <T>(endpoint: string) => request<T>(endpoint),
    post: <T>(endpoint: string, body?: unknown) => request<T>(endpoint, { method: 'POST', body }),
    put: <T>(endpoint: string, body?: unknown) => request<T>(endpoint, { method: 'PUT', body }),
    patch: <T>(endpoint: string, body?: unknown) => request<T>(endpoint, { method: 'PATCH' as any, body }),
    delete: <T>(endpoint: string) => request<T>(endpoint, { method: 'DELETE' }),
}

// ============ Tasks API ============
export const tasksApi = {
    list: () => api.get<Task[]>('/tasks'),
    get: (taskId: string) => api.get<Task>(`/tasks/${taskId}`),
    create: (data: CreateTaskData) => api.post<Task>('/tasks', data),
    start: (taskId: string) => api.post<{ message: string }>(`/tasks/${taskId}/start`),
    pause: (taskId: string) => api.post<{ message: string }>(`/tasks/${taskId}/pause`),
    cancel: (taskId: string) => api.post<{ message: string }>(`/tasks/${taskId}/cancel`),
    delete: (taskId: string) => api.delete<{ message: string }>(`/tasks/${taskId}`),
}

// ============ Accounts API ============
export const accountsApi = {
    list: (params?: {
        status?: string;
        health_status?: string;
        region?: string;
        search?: string;
        start_date?: string;
        end_date?: string;
        usage_status?: string;
        page?: number;
        page_size?: number
    }) => {
        const query = new URLSearchParams()
        if (params?.status) query.set('status', params.status)
        if (params?.health_status) query.set('health_status', params.health_status)
        if (params?.region) query.set('region', params.region)
        if (params?.search) query.set('search', params.search)
        if (params?.start_date) query.set('start_date', params.start_date)
        if (params?.end_date) query.set('end_date', params.end_date)
        if (params?.usage_status) query.set('usage_status', params.usage_status)
        if (params?.page) query.set('page', String(params.page))
        if (params?.page_size) query.set('page_size', String(params.page_size))
        return api.get<Account[]>(`/accounts?${query}`)
    },
    get: (id: number) => api.get<Account>(`/accounts/${id}`),
    getStats: (params?: {
        status?: string;
        health_status?: string;
        region?: string;
        search?: string;
        start_date?: string;
        end_date?: string;
        usage_status?: string;
    }) => {
        const query = new URLSearchParams()
        if (params?.status) query.set('status', params.status)
        if (params?.health_status) query.set('health_status', params.health_status)
        if (params?.region) query.set('region', params.region)
        if (params?.search) query.set('search', params.search)
        if (params?.start_date) query.set('start_date', params.start_date)
        if (params?.end_date) query.set('end_date', params.end_date)
        if (params?.usage_status) query.set('usage_status', params.usage_status)
        return api.get<AccountStats>(`/accounts/count?${query}`)
    },
    delete: (id: number) => api.delete<{ message: string }>(`/accounts/${id}`),
    export: (params?: {
        status?: string;
        health_status?: string;
        region?: string;
        search?: string;
        start_date?: string;
        end_date?: string;
        usage_status?: string;
        format?: 'csv' | 'json';
    }) => {
        const query = new URLSearchParams()
        if (params?.status) query.set('status', params.status)
        if (params?.health_status) query.set('health_status', params.health_status)
        if (params?.region) query.set('region', params.region)
        if (params?.search) query.set('search', params.search)
        if (params?.start_date) query.set('start_date', params.start_date)
        if (params?.end_date) query.set('end_date', params.end_date)
        if (params?.usage_status) query.set('usage_status', params.usage_status)
        if (params?.format) query.set('format', params.format)
        window.open(`${BASE_URL}/accounts/export?${query}`, '_blank')
    },

    // New methods
    refreshStatus: (id: number) => api.post<Account>(`/accounts/${id}/refresh-status`),
    checkin: (id: number) => api.post<Account>(`/accounts/${id}/checkin`),
    batchRefreshStatus: (ids: number[]) => api.post<{ message: string }>('/accounts/batch/refresh-status', { ids }),
    batchCheckin: (ids: number[]) => api.post<{ message: string }>('/accounts/batch/checkin', { ids }),
    batchDelete: (ids: number[]) => api.post<{ message: string }>('/accounts/batch', { ids }),
    toggleGeneration: (id: number, isEnabled: boolean) =>
        api.post<{ message: string }>(`/content/accounts/${id}/toggle?is_enabled=${isEnabled}`),
    batchToggleGeneration: (params: {
        status?: string;
        health_status?: string;
        region?: string;
        search?: string;
        usage_status?: string;
        is_enabled: boolean;
    }) => {
        const query = new URLSearchParams()
        if (params.status) query.set('status', params.status)
        if (params.health_status) query.set('health_status', params.health_status)
        if (params.region) query.set('region', params.region)
        if (params.search) query.set('search', params.search)
        if (params.usage_status) query.set('usage_status', params.usage_status)
        query.set('is_enabled', String(params.is_enabled))
        return api.post<{ message: string; updated: number }>(`/content/accounts/batch-toggle?${query}`)
    },
    manualCreate: (data: { email: string; region: string; session_id: string }) =>
        api.post<Account>('/accounts/manual', data),
    manualImport: (data: { mode: 'csv' | 'txt'; content: string }) =>
        api.post<{ success: number; skipped: number; failed: number; errors: { line: number; email?: string; reason: string }[] }>(
            '/accounts/manual/import',
            data
        ),
}

// ============ Content Generation API ============
export const contentApi = {
    generate: (data: ContentGenerationRequest) => api.post<ContentGenerationJob>('/content/generate', data),
    getModels: (params?: { region?: string }) => {
        const query = new URLSearchParams()
        if (params?.region) query.set('region', params.region)
        return api.get<ContentGenerationModels>(`/content/models?${query}`)
    },
    listJobs: (params?: { job_type?: string; status?: string }) => {
        const query = new URLSearchParams()
        if (params?.job_type) query.set('job_type', params.job_type)
        if (params?.status) query.set('status', params.status)
        return api.get<ContentGenerationJob[]>(`/content/jobs?${query}`)
    },
    getJob: (id: number) => api.get<ContentGenerationJob>(`/content/jobs/${id}`),
    cancelJob: (id: number) => api.post<ContentGenerationJob>(`/content/jobs/${id}/cancel`),
    deleteJob: (id: number) => api.delete<{ message: string }>(`/content/jobs/${id}`),
    batchDeleteJobs: (ids: number[]) => api.post<{ message: string, deleted: number }>('/content/jobs/batch-delete', ids),
    retryJob: (id: number) => api.post<ContentGenerationJob>(`/content/jobs/${id}/retry`),
}

// ============ Proxies API ============
export const proxiesApi = {
    list: () => api.get<ProxyNode[]>('/proxies'),
    sync: () => api.post<{ message: string }>('/proxies/sync'),
    getClashStatus: () => api.get<{ connected: boolean; current_node: string | null }>('/proxies/clash-status'),
    toggle: (id: number) => api.post<ProxyNode>(`/proxies/${id}/toggle`),
    batchToggle: (ids: number[], is_enabled: boolean) =>
        api.post<{ message: string }>(`/proxies/batch-toggle`, { ids, is_enabled }),
    update: (id: number, data: { region_tag?: string; is_enabled?: boolean }) =>
        api.put<ProxyNode>(`/proxies/${id}`, data),
    testLatency: () => api.post<{ message: string }>('/proxies/test-latency'),
    testNodeLatency: (id: number) => api.post<ProxyNode>(`/proxies/${id}/test-latency`),
    // New Pool Methods
    getPoolStatus: () => api.get<{ total: number; active: number; idle: number }>('/proxies/pool/status'),
    reloadPool: () => api.post<{ message: string; count: number }>('/proxies/pool/reload'),
}

// ============ Domains API ============
export const domainsApi = {
    list: () => api.get<Domain[]>('/domains'),
    create: (data: CreateDomainData) => api.post<Domain>('/domains', data),
    update: (id: number, data: Partial<Domain>) => api.put<Domain>(`/domains/${id}`, data),
    delete: (id: number) => api.delete<{ message: string }>(`/domains/${id}`),
    toggle: (id: number) => api.post<Domain>(`/domains/${id}/toggle`),
    test: (id: number) => api.post<{ message: string; success: boolean }>(`/domains/${id}/test`),
}

// ============ Settings API ============
export const settingsApi = {
    get: () => api.get<Settings>('/settings'),
    update: (data: Partial<Settings>) => api.put<{ message: string }>('/settings', data),
}

// ============ Outlook Mailboxes API ============
export const outlookMailboxesApi = {
    list: (page = 1, pageSize = 50) =>
        api.get<OutlookMailboxListResponse>(`/outlook-mailboxes?page=${page}&page_size=${pageSize}`),
    batchCreate: (emails: string[], note?: string) =>
        api.post<{ message: string; success: boolean }>('/outlook-mailboxes/batch', { emails, note }),
    toggle: (id: number, isEnabled: boolean) =>
        api.patch<OutlookMailbox>(`/outlook-mailboxes/${id}`, { is_enabled: isEnabled }),
    delete: (id: number) =>
        api.delete<{ message: string }>(`/outlook-mailboxes/${id}`),
}

// ============ Types ============
export interface Task {
    id: number
    task_id: string
    status: 'created' | 'queued' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed'
    total_count: number
    success_count: number
    failure_count: number
    progress: number
    proxy_strategy?: string
    email_prefix_pattern?: string
    assigned_email?: string
    assigned_proxy_region?: string
    assigned_proxy_name?: string
    retry_count: number
    max_retries: number
    created_at: string
    completed_at?: string
}

export interface CreateTaskData {
    total_count: number
    domain_mode: 'manual' | 'auto_rotate'
    domain_ids?: number[]
    proxy_strategy: 'round_robin' | 'random' | 'least_used';
    email_prefix_pattern: string;
    max_retries: number;
    email_source: 'cloudflare' | 'outlook';
}

export interface Account {
    id: number
    email: string
    password: string
    session_id?: string
    status: 'pending' | 'registering' | 'success' | 'active' | 'failed' | 'banned'
    last_login_status?: 'success' | 'failed'
    is_valid: string
    proxy_node_name: string | null
    region: string | null
    health_status: 'healthy' | 'expired' | 'banned' | 'unknown'
    created_at: string
    task_id?: string

    // 积分相关
    credits_total: number
    credits_gift: number
    credits_purchase: number
    credits_vip: number

    last_credit_check_at?: string
    last_checkin_at?: string

    // 内容生成池
    gen_enabled?: boolean
    gen_enabled_at?: string
    gen_last_used_at?: string
    gen_locked_until?: string
    gen_auto_disabled_reason?: string
}

export interface ContentGenerationRequest {
    job_type: 'image' | 'video'
    prompt: string
    model?: string
    ratio?: string
    resolution?: string
    duration?: number
    input_images?: string[]
    async_mode?: boolean
    function_mode?: string
}

export interface ContentGenerationJob {
    id: number
    job_type: 'image' | 'video'
    status: 'queued' | 'submitting' | 'submitted' | 'processing' | 'success' | 'failed' | 'cancelled'
    prompt?: string
    model?: string
    ratio?: string
    resolution?: string
    duration?: number
    function_mode?: string
    input_images?: string[]
    output_urls?: string[]
    thumbnail_urls?: string[]
    local_urls?: string[]
    error_message?: string
    remote_task_id?: string
    remote_history_id?: string
    remote_kind?: string
    remote_status?: string
    remote_fail_code?: string
    remote_error_message?: string
    account_id?: number
    region?: string
    submitted_at?: string
    finished_at?: string
    created_at?: string
    updated_at?: string
}

export interface ContentGenerationModels {
    region: string
    profile: string
    model_set: string
    image_models: string[]
    video_models: string[]
    source: string
}

export interface AccountStats {
    total: number
    success: number
    failed: number
    pending: number
    success_rate: number
    matched: number
}

// ============ insMind Accounts API ============
export interface InsMindAccount {
    id: number
    email: string
    token?: string
    credits: number
    status: 'active' | 'expired' | 'banned'
    created_at: string
    updated_at: string
}

export const insmindAccountsApi = {
    list: (params?: { status?: string; page?: number; page_size?: number }) => {
        const query = new URLSearchParams()
        if (params?.status) query.set('status', params.status)
        if (params?.page) query.set('page', String(params.page))
        if (params?.page_size) query.set('page_size', String(params.page_size))
        return api.get<InsMindAccount[]>(`/insmind/accounts?${query}`)
    },
    get: (id: number) => api.get<InsMindAccount>(`/insmind/accounts/${id}`),
    getStats: () => api.get<AccountStats>('/insmind/accounts/stats'),
    delete: (id: number) => api.delete<{ message: string }>(`/insmind/accounts/${id}`),
    batchDelete: (ids: number[]) => api.post<{ message: string; deleted: number }>('/insmind/accounts/batch-delete', { ids }),
    autoRegister: () => api.post<{ success: boolean; email?: string; token?: string; user_id?: string; pool_total: number; error?: string }>('/insmind/accounts/auto-register'),
    autoRegisterBatch: (count: number) => api.post<{ total: number; success: number; failed: number; results: any[] }>(`/insmind/accounts/auto-register-batch?count=${count}`),
    generateVideo: (params: { prompt: string; model?: string; duration?: number; resolution?: string; aspect_ratio?: string; image_url?: string }) =>
        api.post<{ success: boolean; task_id?: string; video_url?: string; error?: string; timeout?: boolean }>('/insmind/generate', params),
}

// ============ PhotoGPT Accounts API ============
export interface PhotoGPTAccount {
    id: number
    email: string
    access_token?: string
    credits: number
    credits_used?: number
    status: 'active' | 'expired' | 'banned'
    created_at: string
    updated_at: string
}

export const photogptAccountsApi = {
    list: (params?: { status?: string; page?: number; page_size?: number }) => {
        const query = new URLSearchParams()
        if (params?.status) query.set('status', params.status)
        if (params?.page) query.set('page', String(params.page))
        if (params?.page_size) query.set('page_size', String(params.page_size))
        return api.get<PhotoGPTAccount[]>(`/photogpt/accounts?${query}`)
    },
    getStats: () => api.get<AccountStats>('/photogpt/accounts/stats'),
    delete: (id: number) => api.delete<{ message: string }>(`/photogpt/accounts/${id}`),
    batchDelete: (ids: number[]) => api.post<{ message: string; deleted: number }>('/photogpt/accounts/batch-delete', { ids }),
    autoRegister: () => api.post<{ success: boolean; email?: string; access_token?: string; pool_total: number; error?: string }>('/photogpt/accounts/auto-register'),
    autoRegisterBatch: (count: number) => api.post<{ total: number; success: number; failed: number; results: any[] }>(`/photogpt/accounts/auto-register-batch?count=${count}`),
    getSettings: () => api.get<{ auto_delete_on_exhaust: boolean }>('/photogpt/settings'),
    updateSettings: (data: { auto_delete_on_exhaust: boolean }) => api.put<{ auto_delete_on_exhaust: boolean }>('/photogpt/settings', data),
}

export interface ProxyNode {
    id: number
    name: string
    node_type?: string
    host?: string
    port?: number
    username?: string
    password?: string
    protocol?: string
    source?: string
    region_tag?: string
    is_enabled: boolean
    latency?: number
    is_healthy?: boolean
    status_icon: string
    usage_count: number
    last_tested_at?: string
}

export interface Domain {
    id: number
    domain: string
    cf_zone_id?: string
    is_enabled: boolean
    usage_count: number
    usage_limit: number
    is_available: boolean
    note?: string
    created_at: string
}

export interface CreateDomainData {
    domain: string
    cf_zone_id?: string
    usage_limit?: number
    note?: string
}

export interface Settings {
    insmind_url: string
    insmind_register_timeout: number
    insmind_verification_timeout: number
    insmind_concurrency: number
    max_retry_count: number
    gen_async_enabled: boolean
    gen_image_async_poll_interval: number
    gen_video_async_poll_interval: number
    register_interval_min: number
    register_interval_max: number
    password_length: number
    password_include_special: boolean
    browser_headless: boolean
    clash_controller_url: string
    clash_secret?: string
    clash_proxy_port: number
    clash_proxy_group: string
    proxy_pool_keywords?: string
    mihomo_binary_path?: string
    clash_config_path?: string
    proxy_pool_start_port: number
    proxy_pool_size: number
    ext_proxy_file_path?: string
    cf_account_id?: string
    cf_kv_namespace_id?: string
    cf_api_token?: string
    max_concurrency: number
    // Outlook Manager
    outlook_manager_url?: string
    outlook_manager_api_key?: string
    outlook_poll_interval?: number
    outlook_poll_timeout?: number
}

export interface OutlookMailbox {
    id: number
    email: string
    note?: string
    is_enabled: boolean
    usage_count: number
    last_used_at?: string
    created_at: string
}

export interface OutlookMailboxListResponse {
    total: number
    page: number
    page_size: number
    items: OutlookMailbox[]
}

// ============ PhotoGPT Generation API ============
export interface PhotoGPTGenJob {
    id: number
    status: 'submitting' | 'submitted' | 'processing' | 'success' | 'failed'
    prompt: string
    model: string
    aspect_ratio: string
    resolution: string
    quality: string
    output_num: number
    output_urls?: string[]
    error_message?: string
    created_at: string
    updated_at: string
}

export const photogptGenApi = {
    generate: (params: {
        prompt: string
        aspect_ratio?: string
        output_num?: number
        quality?: string
        resolution?: string
        input_urls?: string[]
    }) => api.post<{ success: boolean; job_id?: number; project_id?: string; error?: string }>('/photogpt/generate', params),

    listJobs: () => api.get<PhotoGPTGenJob[]>('/photogpt/generate/jobs'),

    retryJob: (id: number) => api.post<PhotoGPTGenJob>('/photogpt/generate/retry', { job_id: id }),

    deleteJob: (id: number) => api.delete<{ message: string }>(`/photogpt/generate/jobs/${id}`),

    batchDeleteJobs: (ids: number[]) => api.post<{ deleted: number }>('/photogpt/generate/jobs/batch-delete', { ids }),
}
