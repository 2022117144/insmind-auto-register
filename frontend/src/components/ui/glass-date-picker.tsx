import { useState, useEffect, useRef } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './button';

interface GlassDatePickerProps {
    value: string;
    onChange: (date: string) => void;
    placeholder?: string;
    className?: string;
}

export function GlassDatePicker({ value, onChange, placeholder = "Select date", className }: GlassDatePickerProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [currentDate, setCurrentDate] = useState(new Date());
    const containerRef = useRef<HTMLDivElement>(null);

    // Initialize calendar view based on value or today
    useEffect(() => {
        if (value) {
            const date = new Date(value);
            if (!isNaN(date.getTime())) {
                setCurrentDate(date);
            }
        }
    }, [value]);

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const getDaysInMonth = (year: number, month: number) => new Date(year, month + 1, 0).getDate();
    const getFirstDayOfMonth = (year: number, month: number) => new Date(year, month, 1).getDay();

    const renderCalendar = () => {
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        const daysInMonth = getDaysInMonth(year, month);
        const firstDay = getFirstDayOfMonth(year, month);
        
        const days = [];
        const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

        // Headers
        const weekDays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

        // Empty slots
        for (let i = 0; i < firstDay; i++) {
            days.push(<div key={`empty-${i}`} className="h-8 w-8" />);
        }

        // Days
        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const isSelected = value === dateStr;
            const isToday = new Date().toDateString() === new Date(year, month, day).toDateString();

            days.push(
                <button
                    key={day}
                    onClick={() => {
                        onChange(dateStr);
                        setIsOpen(false);
                    }}
                    className={cn(
                        "h-8 w-8 rounded-full flex items-center justify-center text-xs transition-all duration-200",
                        isSelected 
                            ? "bg-primary text-primary-foreground shadow-lg shadow-primary/25 scale-110 font-bold" 
                            : isToday 
                                ? "bg-accent/50 text-accent-foreground border border-primary/30" 
                                : "hover:bg-accent hover:text-accent-foreground text-muted-foreground"
                    )}
                >
                    {day}
                </button>
            );
        }

        return (
            <div className="p-4 w-[280px]">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                    <button 
                        onClick={() => setCurrentDate(new Date(year, month - 1, 1))}
                        className="p-1 hover:bg-accent rounded-full text-muted-foreground transition-colors"
                    >
                        <ChevronLeft className="h-4 w-4" />
                    </button>
                    <div className="font-medium text-sm text-foreground">
                        {monthNames[month]} {year}
                    </div>
                    <button 
                        onClick={() => setCurrentDate(new Date(year, month + 1, 1))}
                        className="p-1 hover:bg-accent rounded-full text-muted-foreground transition-colors"
                    >
                        <ChevronRight className="h-4 w-4" />
                    </button>
                </div>

                {/* Week days */}
                <div className="grid grid-cols-7 mb-2">
                    {weekDays.map(d => (
                        <div key={d} className="h-8 w-8 flex items-center justify-center text-[10px] uppercase font-bold text-muted-foreground/50">
                            {d}
                        </div>
                    ))}
                </div>

                {/* Grid */}
                <div className="grid grid-cols-7 gap-y-1">
                    {days}
                </div>
                
                {value && (
                    <div className="mt-4 pt-3 border-t border-border/20 flex justify-center">
                        <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-6 text-xs text-muted-foreground hover:text-destructive"
                            onClick={(e) => {
                                e.stopPropagation();
                                onChange('');
                                setIsOpen(false);
                            }}
                        >
                            Clear Date
                        </Button>
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className={cn("relative", className)} ref={containerRef}>
            <div 
                className={cn(
                    "flex items-center gap-2 h-9 px-3 py-1 rounded-md border transition-all duration-200 cursor-pointer group",
                    "bg-background/50 hover:bg-accent/50",
                    isOpen ? "border-primary/50 ring-2 ring-primary/10" : "border-border/50",
                    value ? "text-foreground" : "text-muted-foreground"
                )}
                onClick={() => setIsOpen(!isOpen)}
            >
                <CalendarIcon className={cn("h-4 w-4 transition-colors", value ? "text-primary" : "text-muted-foreground/70")} />
                <span className="text-xs font-medium flex-1 truncate">
                    {value || placeholder}
                </span>
                {value && (
                    <div 
                        role="button"
                        className="p-0.5 rounded-full hover:bg-destructive/10 hover:text-destructive text-muted-foreground/50 transition-colors"
                        onClick={(e) => {
                            e.stopPropagation();
                            onChange('');
                        }}
                    >
                        <X className="h-3 w-3" />
                    </div>
                )}
            </div>

            {isOpen && (
                <div className="absolute top-full left-0 mt-2 z-50 animate-in fade-in zoom-in-95 duration-200 origin-top-left">
                    <div className="bg-[#121214]/80 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden ring-1 ring-black/20">
                        {renderCalendar()}
                    </div>
                </div>
            )}
        </div>
    );
}
