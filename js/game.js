/* ========================================
   Bustabit Clone - Complete Game Engine
   ======================================== */

// ========================================
// Audio Engine (Web Audio API)
// ========================================
const AudioEngine = {
    ctx: null,
    enabled: true,

    init() {
        try {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) { this.enabled = false; }
    },

    play(type) {
        if (!this.enabled || !this.ctx) return;
        if (this.ctx.state === 'suspended') this.ctx.resume();
        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.ctx.destination);

        switch (type) {
            case 'bet':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(800, now);
                osc.frequency.exponentialRampToValueAtTime(1200, now + 0.1);
                gain.gain.setValueAtTime(0.15, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
                osc.start(now);
                osc.stop(now + 0.15);
                break;
            case 'cashout':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(600, now);
                osc.frequency.exponentialRampToValueAtTime(1400, now + 0.15);
                gain.gain.setValueAtTime(0.2, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
                osc.start(now);
                osc.stop(now + 0.25);
                break;
            case 'bust':
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(400, now);
                osc.frequency.exponentialRampToValueAtTime(80, now + 0.5);
                gain.gain.setValueAtTime(0.2, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
                osc.start(now);
                osc.stop(now + 0.5);
                break;
            case 'tick':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(1000, now);
                gain.gain.setValueAtTime(0.05, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
                osc.start(now);
                osc.stop(now + 0.05);
                break;
            case 'countdown':
                osc.type = 'square';
                osc.frequency.setValueAtTime(440, now);
                gain.gain.setValueAtTime(0.08, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
                osc.start(now);
                osc.stop(now + 0.1);
                break;
            case 'start':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(400, now);
                osc.frequency.exponentialRampToValueAtTime(900, now + 0.2);
                gain.gain.setValueAtTime(0.12, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
                osc.start(now);
                osc.stop(now + 0.3);
                break;
        }
    }
};

// ========================================
// Provably Fair System
// ========================================
const ProvablyFair = {
    hashChain: [],
    currentIndex: 0,
    salt: '0000000000000000004d6ec16dafe9d8370958664c1dc422f452892264c59526',

    async sha256(message) {
        const msgBuffer = new TextEncoder().encode(message);
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    },

    async generateHash() {
        const seed = Math.random().toString(36) + Date.now().toString(36);
        return await this.sha256(seed);
    },

    async hashToCrashPoint(hash) {
        const hmacHex = await this.sha256(hash + this.salt);
        const h = parseInt(hmacHex.substring(0, 13), 16);
        const e = Math.pow(2, 52);

        if (h % 33 === 0) return 1.00;

        return Math.max(1, Math.floor((100 * e - h) / (e - h)) / 100);
    },

    async getNextCrash() {
        const hash = await this.generateHash();
        const crash = await this.hashToCrashPoint(hash);
        return { hash, crashPoint: crash };
    }
};

// ========================================
// Simulated Players
// ========================================
const SimPlayers = {
    names: [
        'CryptoKing', 'BitWhale', 'MoonShot', 'DiamondHands', 'SatoshiFan',
        'HODLer99', 'BustOrBoom', '2xOrNothing', 'LuckySeven', 'TheHouse',
        'CashMachine', 'RiskTaker', 'SafePlayer', 'BigBaller', 'NervesOfSteel',
        'GreenCandle', 'BearHunter', 'ApeStrong', 'WhaleTail', 'BitBandit',
        'CoinFlip', 'StackMore', 'DegenPlay', 'EarlyBird', 'NightOwl',
        'SilverFox', 'GoldRush', 'IronNerves', 'CoolHead', 'HotStreak',
        'ChainLink', 'BlockHead', 'HashRate', 'NodeRunner', 'GasFee',
        'TokenKing', 'SmartMoney', 'DumbLuck', 'Yolo420', 'PaperHands'
    ],

    generate(count) {
        const players = [];
        const shuffled = [...this.names].sort(() => Math.random() - 0.5);
        const n = Math.min(count, shuffled.length);
        for (let i = 0; i < n; i++) {
            const bet = this.randomBet();
            const autoCashout = Math.random() < 0.6
                ? (1.1 + Math.random() * 8).toFixed(2)
                : null;
            players.push({
                name: shuffled[i],
                bet: bet,
                autoCashout: autoCashout ? parseFloat(autoCashout) : null,
                cashedOut: false,
                cashoutMultiplier: null,
                profit: null
            });
        }
        return players;
    },

    randomBet() {
        const r = Math.random();
        if (r < 0.3) return Math.floor(10 + Math.random() * 90);
        if (r < 0.7) return Math.floor(100 + Math.random() * 900);
        if (r < 0.9) return Math.floor(1000 + Math.random() * 9000);
        return Math.floor(10000 + Math.random() * 90000);
    }
};

// ========================================
// Chat System
// ========================================
const ChatSystem = {
    messages: [],
    botMessages: [
        "lol busted at 1.00x again",
        "who else is going big this round?",
        "just hit 50x!!!! LETS GO",
        "any strategies that actually work?",
        "martingale is the way",
        "don't gamble more than you can afford",
        "1.5x auto cashout is the safe play",
        "been on a losing streak all day",
        "this game is rigged (jk it's provably fair)",
        "HOLD HOLD HOLD",
        "busted... should have cashed out",
        "100x or bust",
        "going for 10x this round",
        "I just doubled my balance!",
        "small bets, steady profits",
        "who saw that 200x game earlier??",
        "new here, how does this work?",
        "gl everyone",
        "that was close!",
        "playing it safe today",
        "anyone else nervous watching the graph?",
        "2x gang where you at",
        "I can feel a big one coming",
        "rip to everyone who didn't cash out",
        "my heart is racing lol"
    ],

    init() {
        // Seed initial messages
        const initial = [
            { user: 'System', text: 'Welcome to Bustabit! Place your bets and cash out before the crash.', system: true },
            { user: 'CryptoKing', text: 'hey everyone, gl!' },
            { user: 'MoonShot', text: 'just hit 15x last round, feeling lucky' },
            { user: 'SafePlayer', text: '2x auto cashout all day' },
        ];
        initial.forEach(m => this.addMessage(m.user, m.text, m.system));
    },

    addMessage(user, text, isSystem = false) {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        this.messages.push({ user, text, time, system: isSystem });
        this.render();
    },

    render() {
        const container = document.getElementById('chatMessages');
        // Keep last 100 messages
        const msgs = this.messages.slice(-100);
        container.innerHTML = msgs.map(m => {
            if (m.system) {
                return `<div class="chat-message system-msg">
                    <span class="chat-text">${this.escapeHtml(m.text)}</span>
                    <span class="chat-time">${m.time}</span>
                </div>`;
            }
            return `<div class="chat-message">
                <span class="chat-user">${this.escapeHtml(m.user)}</span>
                <span class="chat-text">${this.escapeHtml(m.text)}</span>
                <span class="chat-time">${m.time}</span>
            </div>`;
        }).join('');
        container.scrollTop = container.scrollHeight;
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    randomBotMessage() {
        const user = SimPlayers.names[Math.floor(Math.random() * SimPlayers.names.length)];
        const text = this.botMessages[Math.floor(Math.random() * this.botMessages.length)];
        this.addMessage(user, text);
    }
};

// ========================================
// Graph Renderer
// ========================================
const GraphRenderer = {
    canvas: null,
    ctx: null,
    points: [],
    animationId: null,

    init() {
        this.canvas = document.getElementById('gameCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
    },

    resize() {
        const container = this.canvas.parentElement;
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = container.clientWidth * dpr;
        this.canvas.height = container.clientHeight * dpr;
        this.ctx.scale(dpr, dpr);
        this.canvas.style.width = container.clientWidth + 'px';
        this.canvas.style.height = container.clientHeight + 'px';
    },

    clear() {
        this.points = [];
        const w = this.canvas.width / (window.devicePixelRatio || 1);
        const h = this.canvas.height / (window.devicePixelRatio || 1);
        this.ctx.clearRect(0, 0, w, h);
    },

    addPoint(elapsed, multiplier) {
        this.points.push({ elapsed, multiplier });
    },

    render(currentMultiplier, isBusted = false) {
        const ctx = this.ctx;
        const dpr = window.devicePixelRatio || 1;
        const w = this.canvas.width / dpr;
        const h = this.canvas.height / dpr;

        ctx.clearRect(0, 0, w, h);

        if (this.points.length < 2) return;

        const padding = { top: 40, right: 60, bottom: 40, left: 60 };
        const graphW = w - padding.left - padding.right;
        const graphH = h - padding.top - padding.bottom;

        // Calculate scales
        const maxTime = Math.max(this.points[this.points.length - 1].elapsed, 5000);
        const maxMult = Math.max(currentMultiplier, 2);

        const scaleX = graphW / maxTime;
        const scaleY = graphH / (maxMult - 1);

        // Draw grid
        ctx.strokeStyle = 'rgba(42, 42, 74, 0.4)';
        ctx.lineWidth = 0.5;
        ctx.setLineDash([4, 4]);

        // Horizontal grid lines (multiplier values)
        const multStep = this.getGridStep(maxMult - 1);
        for (let m = 1 + multStep; m <= maxMult; m += multStep) {
            const y = padding.top + graphH - (m - 1) * scaleY;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(w - padding.right, y);
            ctx.stroke();

            ctx.fillStyle = 'rgba(136, 136, 170, 0.6)';
            ctx.font = '11px Source Sans Pro, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(m.toFixed(2) + '×', padding.left - 8, y + 4);
        }

        // Vertical grid lines (time)
        const timeStep = this.getTimeStep(maxTime);
        for (let t = timeStep; t <= maxTime; t += timeStep) {
            const x = padding.left + t * scaleX;
            ctx.beginPath();
            ctx.moveTo(x, padding.top);
            ctx.lineTo(x, h - padding.bottom);
            ctx.stroke();

            ctx.fillStyle = 'rgba(136, 136, 170, 0.6)';
            ctx.font = '11px Source Sans Pro, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText((t / 1000).toFixed(1) + 's', x, h - padding.bottom + 18);
        }

        ctx.setLineDash([]);

        // Draw axes
        ctx.strokeStyle = 'rgba(42, 42, 74, 0.7)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, h - padding.bottom);
        ctx.lineTo(w - padding.right, h - padding.bottom);
        ctx.stroke();

        // 1.00x label
        ctx.fillStyle = 'rgba(136, 136, 170, 0.6)';
        ctx.textAlign = 'right';
        ctx.fillText('1.00×', padding.left - 8, h - padding.bottom + 4);

        // Draw the curve fill
        ctx.beginPath();
        ctx.moveTo(padding.left, h - padding.bottom);
        for (let i = 0; i < this.points.length; i++) {
            const x = padding.left + this.points[i].elapsed * scaleX;
            const y = padding.top + graphH - (this.points[i].multiplier - 1) * scaleY;
            if (i === 0) ctx.lineTo(x, y);
            else ctx.lineTo(x, y);
        }
        const lastX = padding.left + this.points[this.points.length - 1].elapsed * scaleX;
        ctx.lineTo(lastX, h - padding.bottom);
        ctx.closePath();

        const fillColor = isBusted ? 'rgba(237, 78, 78, 0.08)' : 'rgba(0, 231, 1, 0.08)';
        ctx.fillStyle = fillColor;
        ctx.fill();

        // Draw the curve line
        ctx.beginPath();
        for (let i = 0; i < this.points.length; i++) {
            const x = padding.left + this.points[i].elapsed * scaleX;
            const y = padding.top + graphH - (this.points[i].multiplier - 1) * scaleY;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }

        const lineColor = isBusted ? '#ed4e4e' : '#00e701';
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 3;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.stroke();

        // Draw glow on the line
        ctx.strokeStyle = isBusted ? 'rgba(237, 78, 78, 0.3)' : 'rgba(0, 231, 1, 0.3)';
        ctx.lineWidth = 8;
        ctx.stroke();

        // Draw dot at the end
        if (this.points.length > 0 && !isBusted) {
            const last = this.points[this.points.length - 1];
            const x = padding.left + last.elapsed * scaleX;
            const y = padding.top + graphH - (last.multiplier - 1) * scaleY;

            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fillStyle = '#00e701';
            ctx.fill();

            ctx.beginPath();
            ctx.arc(x, y, 10, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(0, 231, 1, 0.2)';
            ctx.fill();
        }
    },

    getGridStep(range) {
        if (range <= 2) return 0.25;
        if (range <= 5) return 0.5;
        if (range <= 10) return 1;
        if (range <= 50) return 5;
        if (range <= 100) return 10;
        if (range <= 500) return 50;
        return 100;
    },

    getTimeStep(maxTime) {
        if (maxTime <= 5000) return 1000;
        if (maxTime <= 15000) return 2000;
        if (maxTime <= 30000) return 5000;
        if (maxTime <= 60000) return 10000;
        return 20000;
    }
};

// ========================================
// Main Game Engine
// ========================================
const Game = {
    // State
    state: 'WAITING', // WAITING, STARTING, IN_PROGRESS, BUSTED
    balance: 100000, // in bits (100 = 100 bits)
    currentMultiplier: 1.00,
    crashPoint: 1.00,
    gameHash: '',
    gameId: 4582391,
    startTime: 0,
    elapsed: 0,
    betAmount: 0,
    hasBet: false,
    hasCashedOut: false,
    cashoutMultiplier: 0,
    countdown: 5,

    // Auto bet
    autoBetting: false,
    autoBetConfig: null,
    autoBetProfit: 0,
    autoBetCurrentBet: 0,

    // Simulated players
    players: [],

    // History
    history: [],

    // Timing
    lastFrameTime: 0,
    tickCounter: 0,

    async init() {
        AudioEngine.init();
        GraphRenderer.init();
        ChatSystem.init();
        this.updateBalance();
        this.generateHistory();
        this.renderHistory();
        this.setupTabs();
        this.setupInputListeners();
        this.startNewRound();

        // Random chat messages
        setInterval(() => {
            if (Math.random() < 0.3) ChatSystem.randomBotMessage();
        }, 4000);

        // Enable audio on first click
        document.addEventListener('click', () => {
            if (AudioEngine.ctx && AudioEngine.ctx.state === 'suspended') {
                AudioEngine.ctx.resume();
            }
        }, { once: true });
    },

    setupTabs() {
        document.querySelectorAll('.tab-bar .tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab-bar .tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                const target = tab.dataset.tab === 'manual' ? 'manualTab' : 'autoTab';
                document.getElementById(target).classList.add('active');
            });
        });

        // Nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const text = link.textContent;
                if (text === 'Leaderboard') {
                    this.showLeaderboard();
                } else if (text === 'FAQ') {
                    this.showFairness();
                }
            });
        });
    },

    setupInputListeners() {
        const betInput = document.getElementById('betAmount');
        const cashoutInput = document.getElementById('autoCashout');

        betInput.addEventListener('input', () => this.updateProfitDisplay());
        cashoutInput.addEventListener('input', () => this.updateProfitDisplay());
        document.getElementById('autoCashoutEnabled').addEventListener('change', () => this.updateProfitDisplay());

        this.updateProfitDisplay();
    },

    updateProfitDisplay() {
        const bet = parseFloat(document.getElementById('betAmount').value) || 0;
        const cashout = parseFloat(document.getElementById('autoCashout').value) || 2;
        const enabled = document.getElementById('autoCashoutEnabled').checked;
        const mult = enabled ? cashout : 2;
        const profit = (bet * mult) - bet;
        document.getElementById('profitDisplay').textContent = `+${profit.toFixed(2)} bits`;
    },

    updateBalance() {
        document.getElementById('balanceAmount').textContent = this.balance.toFixed(2);
    },

    generateHistory() {
        for (let i = 0; i < 20; i++) {
            const crash = this.generateCrashPoint();
            this.history.unshift(crash);
        }
    },

    generateCrashPoint() {
        // Simulate provably fair distribution
        // House edge ~1%
        const r = Math.random();
        if (r < 0.03) return 1.00;
        const e = 0.99; // 1% house edge
        return Math.max(1, Math.floor(100 * e / (1 - r)) / 100);
    },

    renderHistory() {
        const bar = document.getElementById('historyBar');
        bar.innerHTML = this.history.slice(0, 30).map(crash => {
            const cls = crash >= 1.98 ? 'green' : 'red';
            return `<div class="history-item ${cls}">${crash.toFixed(2)}×</div>`;
        }).join('');
    },

    // ========================================
    // Game Loop
    // ========================================
    async startNewRound() {
        this.state = 'STARTING';
        this.currentMultiplier = 1.00;
        this.hasBet = false;
        this.hasCashedOut = false;
        this.cashoutMultiplier = 0;
        this.betAmount = 0;

        // Generate crash point
        this.crashPoint = this.generateCrashPoint();
        this.gameHash = await ProvablyFair.generateHash();
        this.gameId++;

        document.getElementById('gameId').textContent = this.gameId.toLocaleString();
        document.getElementById('gameHash').textContent = this.gameHash.substring(0, 8) + '...';

        // Generate simulated players
        const playerCount = 20 + Math.floor(Math.random() * 25);
        this.players = SimPlayers.generate(playerCount);
        document.getElementById('playerCount').textContent = `${this.players.length} playing`;
        this.renderPlayers();

        // Reset graph
        GraphRenderer.clear();

        // Update button
        this.updateBetButton();

        // Countdown
        this.countdown = 5;
        this.runCountdown();
    },

    runCountdown() {
        const multiplierEl = document.getElementById('currentMultiplier');
        const statusEl = document.getElementById('statusText');

        if (this.countdown > 0) {
            multiplierEl.className = 'multiplier waiting';
            multiplierEl.textContent = `${this.countdown.toFixed(1)}s`;
            statusEl.textContent = 'Starting soon...';
            statusEl.className = 'status-text';

            AudioEngine.play('countdown');

            this.countdown -= 0.1;
            setTimeout(() => this.runCountdown(), 100);
        } else {
            this.startGame();
        }
    },

    startGame() {
        this.state = 'IN_PROGRESS';
        this.startTime = performance.now();
        this.elapsed = 0;
        this.tickCounter = 0;

        AudioEngine.play('start');

        // Auto bet
        if (this.autoBetting) {
            this.executeAutoBet();
        }

        this.updateBetButton();
        this.gameLoop();
    },

    gameLoop() {
        if (this.state !== 'IN_PROGRESS') return;

        const now = performance.now();
        this.elapsed = now - this.startTime;

        // Bustabit multiplier formula: exponential growth
        // e^(0.00006 * elapsed_ms)
        this.currentMultiplier = Math.pow(Math.E, 0.00006 * this.elapsed);
        this.currentMultiplier = Math.floor(this.currentMultiplier * 100) / 100;

        // Update display
        const multiplierEl = document.getElementById('currentMultiplier');
        multiplierEl.className = 'multiplier';
        multiplierEl.textContent = this.currentMultiplier.toFixed(2) + '×';

        const statusEl = document.getElementById('statusText');
        statusEl.textContent = '';
        statusEl.className = 'status-text';

        // Add graph point
        GraphRenderer.addPoint(this.elapsed, this.currentMultiplier);
        GraphRenderer.render(this.currentMultiplier, false);

        // Sound tick at certain milestones
        this.tickCounter++;
        if (this.tickCounter % 30 === 0) {
            const mInt = Math.floor(this.currentMultiplier);
            if (mInt > 1 && mInt !== this._lastTickMult) {
                AudioEngine.play('tick');
                this._lastTickMult = mInt;
            }
        }

        // Check auto-cashout for player
        if (this.hasBet && !this.hasCashedOut) {
            const autoCashoutEnabled = document.getElementById('autoCashoutEnabled').checked;
            const autoCashoutValue = parseFloat(document.getElementById('autoCashout').value);
            if (autoCashoutEnabled && this.currentMultiplier >= autoCashoutValue) {
                this.cashOut();
            }
        }

        // Simulate other players cashing out
        this.simulatePlayerCashouts();

        // Check if busted
        if (this.currentMultiplier >= this.crashPoint) {
            this.bust();
            return;
        }

        // Update bet button
        this.updateBetButton();

        requestAnimationFrame(() => this.gameLoop());
    },

    simulatePlayerCashouts() {
        this.players.forEach(p => {
            if (p.cashedOut) return;
            // Auto cashout
            if (p.autoCashout && this.currentMultiplier >= p.autoCashout) {
                p.cashedOut = true;
                p.cashoutMultiplier = p.autoCashout;
                p.profit = Math.floor(p.bet * p.autoCashout) - p.bet;
                this.renderPlayers();
                return;
            }
            // Random manual cashout
            if (!p.autoCashout && Math.random() < 0.002 && this.currentMultiplier > 1.2) {
                p.cashedOut = true;
                p.cashoutMultiplier = this.currentMultiplier;
                p.profit = Math.floor(p.bet * this.currentMultiplier) - p.bet;
                this.renderPlayers();
            }
        });
    },

    bust() {
        this.state = 'BUSTED';
        this.currentMultiplier = this.crashPoint;

        AudioEngine.play('bust');

        const multiplierEl = document.getElementById('currentMultiplier');
        multiplierEl.className = 'multiplier bust';
        multiplierEl.textContent = this.crashPoint.toFixed(2) + '×';

        const statusEl = document.getElementById('statusText');
        statusEl.textContent = 'BUSTED';
        statusEl.className = 'status-text bust';

        // Final graph render
        GraphRenderer.addPoint(this.elapsed, this.crashPoint);
        GraphRenderer.render(this.crashPoint, true);

        // Mark remaining players as busted
        this.players.forEach(p => {
            if (!p.cashedOut) {
                p.profit = -p.bet;
            }
        });
        this.renderPlayers();

        // Player lost if didn't cash out
        if (this.hasBet && !this.hasCashedOut) {
            ChatSystem.addMessage('System', `Game crashed at ${this.crashPoint.toFixed(2)}×. You lost ${this.betAmount.toFixed(0)} bits.`, true);
            // Auto bet loss handling
            if (this.autoBetting) {
                this.autoBetProfit -= this.betAmount;
                this.handleAutoBetResult(false);
            }
        } else if (this.hasBet && this.hasCashedOut) {
            if (this.autoBetting) {
                this.handleAutoBetResult(true);
            }
        }

        // Add to history
        this.history.unshift(this.crashPoint);
        if (this.history.length > 50) this.history.pop();
        this.renderHistory();

        this.updateBetButton();

        // Start next round after delay
        setTimeout(() => this.startNewRound(), 3000);
    },

    // ========================================
    // Betting Logic
    // ========================================
    placeBet() {
        if (this.hasBet) {
            // Already bet - try to cash out
            if (this.state === 'IN_PROGRESS' && !this.hasCashedOut) {
                this.cashOut();
            }
            return;
        }

        const amount = parseFloat(document.getElementById('betAmount').value);
        if (isNaN(amount) || amount <= 0) return;
        if (amount > this.balance) {
            ChatSystem.addMessage('System', 'Insufficient balance!', true);
            return;
        }

        this.betAmount = amount;
        this.balance -= amount;
        this.updateBalance();
        this.hasBet = true;

        AudioEngine.play('bet');

        // Add player to the list
        this.players.unshift({
            name: 'Player_1337',
            bet: amount,
            autoCashout: document.getElementById('autoCashoutEnabled').checked
                ? parseFloat(document.getElementById('autoCashout').value)
                : null,
            cashedOut: false,
            cashoutMultiplier: null,
            profit: null,
            isPlayer: true
        });
        this.renderPlayers();

        this.updateBetButton();
    },

    cashOut() {
        if (!this.hasBet || this.hasCashedOut || this.state !== 'IN_PROGRESS') return;

        this.hasCashedOut = true;
        this.cashoutMultiplier = this.currentMultiplier;
        const winnings = this.betAmount * this.currentMultiplier;
        this.balance += winnings;
        this.updateBalance();

        AudioEngine.play('cashout');

        const profit = winnings - this.betAmount;
        ChatSystem.addMessage('System', `You cashed out at ${this.currentMultiplier.toFixed(2)}× and won ${profit.toFixed(2)} bits!`, true);

        if (this.autoBetting) {
            this.autoBetProfit += profit;
        }

        // Update player in list
        const playerEntry = this.players.find(p => p.isPlayer);
        if (playerEntry) {
            playerEntry.cashedOut = true;
            playerEntry.cashoutMultiplier = this.currentMultiplier;
            playerEntry.profit = profit;
        }
        this.renderPlayers();

        this.updateBetButton();
    },

    updateBetButton() {
        const btn = document.getElementById('betButton');
        const text = document.getElementById('betButtonText');
        const sub = document.getElementById('betButtonSub');

        btn.className = 'btn-bet';
        btn.disabled = false;

        if (this.state === 'STARTING') {
            if (this.hasBet) {
                text.textContent = 'Cancel Bet';
                sub.textContent = `(${this.betAmount.toFixed(0)} bits)`;
                btn.className = 'btn-bet btn-waiting';
                btn.onclick = () => this.cancelBet();
            } else {
                text.textContent = 'Place Bet';
                sub.textContent = '(Next round)';
                btn.onclick = () => this.placeBet();
            }
        } else if (this.state === 'IN_PROGRESS') {
            if (this.hasBet && !this.hasCashedOut) {
                const profit = (this.betAmount * this.currentMultiplier - this.betAmount).toFixed(2);
                text.textContent = `Cash Out`;
                sub.textContent = `${this.currentMultiplier.toFixed(2)}× (+${profit})`;
                btn.className = 'btn-bet btn-cashout';
                btn.onclick = () => this.cashOut();
            } else if (this.hasCashedOut) {
                text.textContent = `Cashed Out @ ${this.cashoutMultiplier.toFixed(2)}×`;
                sub.textContent = '';
                btn.disabled = true;
            } else {
                text.textContent = 'Place Bet';
                sub.textContent = '(Next round)';
                btn.onclick = () => this.placeBet();
            }
        } else if (this.state === 'BUSTED') {
            if (this.hasBet && !this.hasCashedOut) {
                text.textContent = `Busted @ ${this.crashPoint.toFixed(2)}×`;
                sub.textContent = `(-${this.betAmount.toFixed(0)} bits)`;
                btn.disabled = true;
                btn.className = 'btn-bet btn-waiting';
            } else if (this.hasCashedOut) {
                text.textContent = `Cashed Out @ ${this.cashoutMultiplier.toFixed(2)}×`;
                sub.textContent = '';
                btn.disabled = true;
            } else {
                text.textContent = 'Waiting...';
                sub.textContent = '';
                btn.disabled = true;
            }
        }
    },

    cancelBet() {
        if (this.state !== 'STARTING' || !this.hasBet) return;
        this.balance += this.betAmount;
        this.updateBalance();
        this.hasBet = false;
        this.betAmount = 0;
        // Remove player from list
        this.players = this.players.filter(p => !p.isPlayer);
        this.renderPlayers();
        this.updateBetButton();
    },

    // ========================================
    // Auto Bet
    // ========================================
    toggleAutoBet() {
        const btn = document.getElementById('autoBetButton');
        if (this.autoBetting) {
            this.autoBetting = false;
            btn.textContent = 'Start Autobet';
            btn.classList.remove('active');
            ChatSystem.addMessage('System', 'Autobet stopped.', true);
            return;
        }

        const baseBet = parseFloat(document.getElementById('autoBaseBet').value);
        const autoCashout = parseFloat(document.getElementById('autoAutoCashout').value);
        const onWin = document.querySelector('input[name="onWin"]:checked').value;
        const onLoss = document.querySelector('input[name="onLoss"]:checked').value;
        const onWinIncrease = parseFloat(document.getElementById('onWinIncrease').value) || 0;
        const onLossIncrease = parseFloat(document.getElementById('onLossIncrease').value) || 0;
        const stopProfit = parseFloat(document.getElementById('stopProfit').value) || Infinity;
        const stopLoss = parseFloat(document.getElementById('stopLoss').value) || Infinity;

        if (isNaN(baseBet) || baseBet <= 0 || isNaN(autoCashout) || autoCashout < 1.01) {
            ChatSystem.addMessage('System', 'Invalid autobet settings.', true);
            return;
        }

        this.autoBetConfig = {
            baseBet, autoCashout, onWin, onLoss,
            onWinIncrease, onLossIncrease,
            stopProfit, stopLoss
        };
        this.autoBetCurrentBet = baseBet;
        this.autoBetProfit = 0;
        this.autoBetting = true;

        btn.textContent = 'Stop Autobet';
        btn.classList.add('active');
        ChatSystem.addMessage('System', `Autobet started: ${baseBet} bits @ ${autoCashout}×`, true);

        // If we're in the starting phase, place the bet now
        if (this.state === 'STARTING') {
            this.executeAutoBet();
        }
    },

    executeAutoBet() {
        if (!this.autoBetting || this.hasBet) return;

        const bet = this.autoBetCurrentBet;
        if (bet > this.balance) {
            this.autoBetting = false;
            document.getElementById('autoBetButton').textContent = 'Start Autobet';
            document.getElementById('autoBetButton').classList.remove('active');
            ChatSystem.addMessage('System', 'Autobet stopped: insufficient balance.', true);
            return;
        }

        // Set the bet amount and auto cashout in the manual tab
        document.getElementById('betAmount').value = bet.toFixed(0);
        document.getElementById('autoCashout').value = this.autoBetConfig.autoCashout.toFixed(2);
        document.getElementById('autoCashoutEnabled').checked = true;

        this.placeBet();
    },

    handleAutoBetResult(won) {
        if (!this.autoBetting) return;

        const cfg = this.autoBetConfig;

        // Check stop conditions
        if (this.autoBetProfit >= cfg.stopProfit) {
            this.autoBetting = false;
            document.getElementById('autoBetButton').textContent = 'Start Autobet';
            document.getElementById('autoBetButton').classList.remove('active');
            ChatSystem.addMessage('System', `Autobet stopped: profit target reached (${this.autoBetProfit.toFixed(2)} bits)`, true);
            return;
        }
        if (-this.autoBetProfit >= cfg.stopLoss) {
            this.autoBetting = false;
            document.getElementById('autoBetButton').textContent = 'Start Autobet';
            document.getElementById('autoBetButton').classList.remove('active');
            ChatSystem.addMessage('System', `Autobet stopped: stop loss reached (${this.autoBetProfit.toFixed(2)} bits)`, true);
            return;
        }

        if (won) {
            if (cfg.onWin === 'reset') {
                this.autoBetCurrentBet = cfg.baseBet;
            } else {
                this.autoBetCurrentBet *= (1 + cfg.onWinIncrease / 100);
            }
        } else {
            if (cfg.onLoss === 'reset') {
                this.autoBetCurrentBet = cfg.baseBet;
            } else {
                this.autoBetCurrentBet *= (1 + cfg.onLossIncrease / 100);
            }
        }

        this.autoBetCurrentBet = Math.floor(this.autoBetCurrentBet);
        if (this.autoBetCurrentBet < 1) this.autoBetCurrentBet = 1;
    },

    // ========================================
    // Player List Rendering
    // ========================================
    renderPlayers() {
        const container = document.getElementById('playersList');

        // Sort: player first, then cashed out, then by bet size
        const sorted = [...this.players].sort((a, b) => {
            if (a.isPlayer && !b.isPlayer) return -1;
            if (!a.isPlayer && b.isPlayer) return 1;
            if (a.cashedOut && !b.cashedOut) return -1;
            if (!a.cashedOut && b.cashedOut) return 1;
            return b.bet - a.bet;
        });

        container.innerHTML = sorted.map(p => {
            const cashedOutClass = p.cashedOut ? 'cashed-out' : '';
            const nameClass = p.isPlayer ? 'style="color: #f0b90b"' : '';
            let profitHtml;
            if (p.cashedOut && p.profit !== null) {
                profitHtml = `<span class="player-profit positive">+${p.profit.toFixed(0)} @ ${p.cashoutMultiplier.toFixed(2)}×</span>`;
            } else if (p.profit !== null && p.profit < 0) {
                profitHtml = `<span class="player-profit negative">${p.profit.toFixed(0)}</span>`;
            } else {
                profitHtml = `<span class="player-profit negative">-</span>`;
            }

            return `<div class="player-row ${cashedOutClass}">
                <span class="player-name" ${nameClass}>${p.isPlayer ? '★ ' : ''}${p.name}</span>
                <span class="player-bet">${p.bet.toLocaleString()}</span>
                ${profitHtml}
            </div>`;
        }).join('');

        document.getElementById('playerCount').textContent = `${this.players.length} playing`;
    },

    // ========================================
    // Leaderboard
    // ========================================
    showLeaderboard() {
        const body = document.getElementById('leaderboardBody');
        const leaderboard = SimPlayers.names.slice(0, 15).map((name, i) => {
            const wagered = Math.floor(50000 + Math.random() * 500000);
            const profitPct = (Math.random() - 0.4) * 100;
            const profit = Math.floor(wagered * profitPct / 100);
            return { name, wagered, profit };
        }).sort((a, b) => b.profit - a.profit);

        body.innerHTML = leaderboard.map((p, i) => {
            const profitColor = p.profit >= 0 ? 'color: var(--accent-green)' : 'color: var(--accent-red)';
            return `<tr>
                <td>${i + 1}</td>
                <td style="color: var(--accent-blue); font-weight: 600">${p.name}</td>
                <td>${p.wagered.toLocaleString()} bits</td>
                <td style="${profitColor}; font-weight: 600">${p.profit >= 0 ? '+' : ''}${p.profit.toLocaleString()} bits</td>
            </tr>`;
        }).join('');

        document.getElementById('leaderboardModal').classList.add('active');
    },

    showFairness() {
        document.getElementById('fairnessModal').classList.add('active');
    }
};

// ========================================
// Global Functions (called from HTML)
// ========================================
function placeBet() { Game.placeBet(); }
function toggleAutoBet() { Game.toggleAutoBet(); }
function showFairness() { Game.showFairness(); }
function closeFairness() { document.getElementById('fairnessModal').classList.remove('active'); }
function closeLeaderboard() { document.getElementById('leaderboardModal').classList.remove('active'); }

function adjustBet(factor) {
    const input = document.getElementById('betAmount');
    const val = parseFloat(input.value) || 0;
    input.value = Math.max(1, Math.floor(val * factor));
    Game.updateProfitDisplay();
}
function setMaxBet() {
    document.getElementById('betAmount').value = Math.floor(Game.balance);
    Game.updateProfitDisplay();
}

function handleChatKey(e) {
    if (e.key === 'Enter') sendChat();
}
function sendChat() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    ChatSystem.addMessage('Player_1337', text);
    input.value = '';
}

async function verifyGame() {
    const hash = document.getElementById('verifyHash').value;
    const salt = document.getElementById('verifySalt').value;
    if (!hash) return;
    const result = await ProvablyFair.hashToCrashPoint(hash);
    const resultEl = document.getElementById('verifyResult');
    resultEl.style.background = result >= 1.98 ? 'rgba(0, 231, 1, 0.1)' : 'rgba(237, 78, 78, 0.1)';
    resultEl.style.color = result >= 1.98 ? 'var(--accent-green)' : 'var(--accent-red)';
    resultEl.textContent = `Crash Point: ${result.toFixed(2)}×`;
}

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});

// ========================================
// Initialize
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    Game.init();
});
