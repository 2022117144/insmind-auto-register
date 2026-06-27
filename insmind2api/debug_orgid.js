const http = require('http');

http.get('http://127.0.0.1:8005/api/insmind/accounts', (res) => {
    let d = '';
    res.on('data', (c) => d += c.toString());
    res.on('end', () => {
        const raw = JSON.parse(d);
        raw.forEach(a => {
            console.log('email:', a.email);
            console.log('  org_id (raw):', JSON.stringify(a.org_id));
            console.log('  org_id type:', typeof a.org_id);
            console.log('  org_id truthy:', !!a.org_id);
            console.log('');
        });
        process.exit(0);
    });
}).on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });