const { build } = require('vite');
build({
    root: __dirname,
    build: {
        outDir: 'dist',
        emptyOutDir: true,
    },
}).then(result => {
    console.log('BUILD SUCCESS');
    console.log(JSON.stringify(result, null, 2));
}).catch(err => {
    console.error('BUILD FAILED:', err.message);
    process.exit(1);
});