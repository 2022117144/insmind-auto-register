const http = require('http');
new Promise((resolve, reject) => {
    const req = http.get('http://127.0.0.1:8005/api/insmind/accounts', (res) => {
        let d = '';
        res.on('data', (c) => d += c.toString());
        res.on('end', () => resolve(d));
    });
    req.on('error', reject);
    req.setTimeout(5000, () => { req.destroy(new Error('Timeout')); });
}).then(data => {
    const raw = JSON.parse(data);
    const accounts = raw.map(a => ({
        email: a.email || '',
        token: a.token || '',
        userId: a.user_id || a.userId || '0',
        credits: a.credits || 0,
        refreshToken: a.refresh_token || a.refreshToken,
        orgId: a.org_id || a.orgId,
        tokenExpiresAt: undefined,
    }));
    accounts.forEach(a => {
        console.log(`${a.email}  orgId=${a.orgId ? a.orgId.substring(0,25) : 'NONE'}`);
    });
});