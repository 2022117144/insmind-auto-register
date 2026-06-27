import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
    ChevronLeft,
    ChevronRight,
    Zap
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { routes, RouteConfig } from '@/config/routes';
import { useLanguage } from '@/contexts/LanguageContext';

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> { }

export function Sidebar({ className }: SidebarProps) {
    const { pathname } = useLocation();
    const [collapsed, setCollapsed] = useState(false);
    const { t } = useLanguage();

    // Group routes by section
    const sections = routes.reduce((acc, route) => {
        if (!route.showInSidebar) return acc;
        const section = route.section || 'Other';
        if (!acc[section]) acc[section] = [];
        acc[section].push(route);
        return acc;
    }, {} as Record<string, RouteConfig[]>);

    const sectionOrder = ['Core', 'Management', 'Monitoring', 'Settings'];

    // Section name mappings
    const sectionTranslations: Record<string, string> = {
        'Core': t('nav.status'),
        'Management': t('common.actions'),
        'Monitoring': t('nav.logs'),
        'Settings': t('nav.settings')
    };

    return (
        <div className={cn(
            "relative flex h-full flex-col bg-sidebar transition-all duration-300 ease-in-out border-r border-border/10",
            collapsed ? "w-[70px]" : "w-64",
            className
        )}>
            {/* Collapse Toggle */}
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setCollapsed(!collapsed)}
                className="absolute -right-3 top-20 z-50 h-6 w-6 rounded-full border border-border/20 bg-card p-0 hover:bg-accent"
            >
                {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
            </Button>

            {/* Logo Section */}
            <div className={cn("flex h-16 items-center px-4", collapsed ? "justify-center" : "px-6")}>
                <Link to="/" className="flex items-center gap-3 font-bold text-base tracking-tight text-foreground">
                    <div className="h-8 w-8 rounded-lg bg-foreground flex items-center justify-center text-background shadow-lg shadow-black/20">
                        <Zap className="h-4.5 w-4.5 fill-current" />
                    </div>
                    {!collapsed && <span className="whitespace-nowrap">insMind Auto</span>}
                </Link>
            </div>

            {/* Navigation Body */}
            <div className="flex-1 overflow-y-auto pt-4 px-3 space-y-6">
                {sectionOrder.map((sectionName) => {
                    const sectionRoutes = sections[sectionName];
                    if (!sectionRoutes) return null;

                    return (
                        <div key={sectionName} className="space-y-1">
                            {!collapsed && (
                                <h4 className="px-3 mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/20">
                                    {sectionTranslations[sectionName] || sectionName}
                                </h4>
                            )}
                            <div className="space-y-1">
                                {sectionRoutes.map((route) => {
                                    const Icon = route.icon;
                                    const active = pathname === route.path;
                                    return (
                                        <Link
                                            key={route.path}
                                            to={route.path}
                                            className={cn(
                                                "flex items-center rounded-lg transition-all group",
                                                collapsed ? "justify-center h-10 w-10 mx-auto" : "gap-3 px-3 py-2.5",
                                                active
                                                    ? "bg-secondary text-foreground shadow-sm"
                                                    : "text-muted-foreground/60 hover:bg-muted/50 hover:text-foreground"
                                            )}
                                            title={collapsed ? t(route.i18nKey as any) : undefined}
                                        >
                                            <Icon className={cn(
                                                "h-5 w-5 shrink-0",
                                                active ? "text-foreground" : "group-hover:text-foreground"
                                            )} />
                                            {!collapsed && <span className="text-sm font-medium">{t(route.i18nKey as any)}</span>}
                                        </Link>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Bottom Footer Section (Optional, can be used for versioning or support) */}
            <div className="p-3 border-t border-border/10">
                {!collapsed && (
                    <div className="px-3 py-2 text-[10px] text-muted-foreground/30 font-medium">
                        v2.1.0 Stable
                    </div>
                )}
            </div>
        </div>
    );
}
