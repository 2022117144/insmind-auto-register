const { SocksProxyAgent } = require('socks-proxy-agent');
const axios = require('axios');

async function test() {
    const proxyUrl = "socks5://sbgeqqsndatacenter:phvr5382iodi@142.111.34.227:6192";
    console.log("Testing proxy:", proxyUrl);
    const agent = new SocksProxyAgent(proxyUrl);
    try {
        const res = await axios.get("http://ip-api.com/json/", {
            httpAgent: agent,
            httpsAgent: agent,
            proxy: false,
            timeout: 10000
        });
        console.log("Success:", res.data);
    } catch (err) {
        console.error("Error:", err.message);
    }
}
test();
