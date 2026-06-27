
import { useEffect, useRef } from 'react';

export function usePolling(callback: () => void, interval: number | null) {
    const savedCallback = useRef(callback);

    // Remember the latest callback.
    useEffect(() => {
        savedCallback.current = callback;
    }, [callback]);

    // Set up the interval.
    useEffect(() => {
        if (interval !== null) {
            const id = setInterval(() => savedCallback.current(), interval);
            return () => clearInterval(id);
        }
    }, [interval]);
}
