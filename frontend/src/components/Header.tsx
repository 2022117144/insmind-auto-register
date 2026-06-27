import { useLocation } from "react-router-dom";
import { routes } from "@/config/routes";

export function Header() {
    const { pathname } = useLocation();

    const getPageTitle = () => {
        const route = routes.find(r => r.path === pathname);
        return route ? route.title : 'insMind Auto';
    };

    return (
        <header className="sticky top-0 z-50 w-full border-b border-border/10 bg-background/80 backdrop-blur-sm">
            <div className="flex h-16 items-center px-8">
                <h2 className="text-xl font-bold tracking-tight">{getPageTitle()}</h2>
                <div className="ml-auto flex items-center space-x-4">
                    {/* Header items */}
                </div>
            </div>
        </header>
    );
}
