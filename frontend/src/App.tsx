import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import { routes } from './config/routes'

function App() {
    return (
        <Routes>
            <Route path="/" element={<Layout />}>
                {routes.map((route) => (
                    <Route
                        key={route.path}
                        path={route.path === '/' ? undefined : route.path.replace(/^\//, '')}
                        index={route.path === '/'}
                        element={route.element}
                    />
                ))}
                <Route path="home" element={<Navigate to="/" replace />} />
                <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
        </Routes>
    )
}

export default App
