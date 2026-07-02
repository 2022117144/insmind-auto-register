import images from "./images.ts";
import ping from "./ping.ts";
import token from './token.ts';
import models from './models.ts';
import videos from './videos.ts';
import tasks from './tasks.ts';
import insmindRoutes from '@/adapters/insmind/insmind-router.ts';
import frontendRoutes from './frontend.ts';
import contentRoutes from './content.ts';

export default [
    {
        get: {
            '/': async () => {
                return {
                    service: 'insmind-api',
                    status: 'running',
                    version: '1.0.0',
                    description: '免费的AI图像和视频生成API服务 - 基于insMind逆向工程',
                    endpoints: {
                        // OpenAI 兼容端点
                        images: '/v1/images/generations',
                        compositions: '/v1/images/compositions',
                        videos: '/v1/videos/generations',
                        tasks: '/v1/tasks/:id',
                        models: '/v1/models',
                        health: '/ping',
                        // insMind 风格端点
                        'insmind:drawing': '/api/ai/drawing',
                        'insmind:video': '/api/ai/video/generate',
                        'insmind:models': '/api/models',
                        'insmind:health': '/api/health',
                        'insmind:tasks': '/api/tasks/:id',
                        // 前端兼容端点
                        'frontend:dashboard': '/api/dashboard/stats',
                        'frontend:accounts': '/api/accounts',
                        'frontend:tasks': '/api/tasks',
                        'frontend:proxies': '/api/proxies',
                        'frontend:domains': '/api/domains',
                        'frontend:settings': '/api/settings',
                        'frontend:outlook': '/api/outlook-mailboxes',
                        'frontend:content:generate': '/api/content/generate',
                        'frontend:content:models': '/api/content/models',
                        'frontend:content:jobs': '/api/content/jobs',
                    }
                };
            }
        }
    },
    images,
    ping,
    token,
    models,
    videos,
    tasks,
    ...insmindRoutes,
    ...contentRoutes,
    ...frontendRoutes,
];