请审查以下前端 TypeScript/TSX 文件。

项目背景: insMind (稿定设计海外版) 自动注册系统前端
文件路径: frontend/src/config/routes.tsx
文件类型: routes

审查重点：
- routes/translations 文件：检查路由配置、导入路径、翻译键是否完整
- 页面组件文件：检查 API 对接、UI 一致性、错误处理、状态管理
- 确认无遗留 Dreamina 名称 (jimeng、dreamina 等)

文件内容:
```typescript
import {
    LayoutDashboard,
    Zap,
    Users,
    ShieldCheck,
    Globe,
    Mail,
    History,
    Settings,
    Sparkles,
    Fingerprint
} from 'lucide-react';
import Dashboard from '../pages/Dashboard';
import Tasks from '../pages/Tasks';
import Accounts from '../pages/Accounts';
import InsMindAccounts from '../pages/InsMindAccounts';
import Proxies from '../pages/Proxies';
import Domains from '../pages/Domains';
import OutlookMailboxes from '../pages/OutlookMailboxes';
import Logs from '../pages/Logs';
import SettingsPage from '../pages/Settings';
import ContentGeneration from '../pages/ContentGeneration';

export interface RouteConfig {
    path: string;
    title: string;
    i18nKey: string;
    element: React.ReactNode;
    icon?: any;
    showInSidebar?: boolean;
    section?: string;
}

export const routes: RouteConfig[] = [
    {
        path: '/',
        title: 'Dashboard',
        i18nKey: 'nav.dashboard',
        element: <Dashboard />,
        icon: LayoutDashboard,
        showInSidebar: true,
        section: 'Core'
    },
    {
        path: '/tasks',
        title: 'Registration Tasks',
        i18nKey: 'nav.tasks',
        element: <Tasks />,
        icon: Zap,
        showInSidebar: true,
        section: 'Core'
    },
    {
        path: '/accounts',
        title: 'Account Management',
        i18nKey: 'nav.accounts',
        element: <Accounts />,
        icon: Users,
        showInSidebar: true,
        section: 'Management'
    },
    {
        path: '/insmind-accounts',
        title: 'insMind Accounts',
        i18nKey: 'nav.insmind_accounts',
        element: <InsMindAccounts />,
        icon: Fingerprint,
        showInSidebar: true,
        section: 'Management'
    },
    {
        path: '/proxies',
        title: 'Proxy Pool',
        i18nKey: 'nav.proxies',
        element: <Proxies />,
        icon: ShieldCheck,
        showInSidebar: true,
        section: 'Management'
    },
    {
        path: '/domains',
        title: 'Domain Center',
        i18nKey: 'nav.domains',
        element: <Domains />,
        icon: Globe,
        showInSidebar: true,
        section: 'Management'
    },
    {
        path: '/outlook-mailboxes',
        title: 'Outlook Mailboxes',
        i18nKey: 'nav.outlook_mailboxes',
        element: <OutlookMailboxes />,
        icon: Mail,
        showInSidebar: true,
        section: 'Management'
    },
    {
        path: '/content',
        title: 'Content Generation',
        i18nKey: 'nav.generate',
        element: <ContentGeneration />,
        icon: Sparkles,
        showInSidebar: true,
        section: 'Core'
    },
    {
        path: '/logs',
        title: 'Running Logs',
        i18nKey: 'nav.logs',
        element: <Logs />,
        icon: History,
        showInSidebar: true,
        section: 'Monitoring'
    },
    {
        path: '/settings',
        title: 'Settings',
        i18nKey: 'nav.settings',
        element: <SettingsPage />,
        icon: Settings,
        showInSidebar: true,
        section: 'Settings'
    }
];

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
