document.addEventListener('DOMContentLoaded', () => {
    const loginWrapper = document.getElementById('login-container');
    const dashboardWrapper = document.getElementById('dashboard-container');
    const loginForm = document.getElementById('login-form');
    const passwordInput = document.getElementById('password');
    const loginError = document.getElementById('login-error');
    const logoutBtn = document.getElementById('logout-btn');
    const refreshBtn = document.getElementById('refresh-services-btn');
    const vpsHostname = document.getElementById('vps-hostname');

    // Processes modal elements
    const processModal = document.getElementById('process-modal');
    const viewProcessesBtn = document.getElementById('view-processes-btn');
    const closeProcessModalBtn = document.getElementById('close-process-modal-btn');
    const refreshProcessesBtn = document.getElementById('refresh-processes-btn');
    const processSearchInput = document.getElementById('process-search-input');
    const processTableBody = document.getElementById('process-table-body');

    let metricsInterval = null;
    let runningProcessesData = [];
    const inlineTerminalLogs = {}; // Store terminal outputs per serviceId
    const inlineTerminalVisible = {}; // Store open state per serviceId

    function getAuthToken() {
        return localStorage.getItem('vps_session_token') || '';
    }

    async function authFetch(url, options = {}) {
        const token = getAuthToken();
        options.headers = options.headers || {};
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }
        options.credentials = 'same-origin';
        return fetch(url, options);
    }

    if (vpsHostname) {
        vpsHostname.textContent = window.location.hostname || 'Server Connected';
    }

    checkAuthStatus();

    async function checkAuthStatus() {
        try {
            const res = await authFetch('/manager/api/auth/check');
            const data = await res.json();
            if (data.authenticated) {
                showDashboard();
            } else {
                showLogin();
            }
        } catch (e) {
            showLogin();
        }
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginError.classList.add('hidden');
        const pass = passwordInput.value.trim();
        if (!pass) return;

        const formData = new FormData();
        formData.append('password', pass);

        try {
            const res = await fetch('/manager/api/auth/login', {
                method: 'POST',
                body: formData
            });

            if (res.ok) {
                const data = await res.json();
                if (data.token) {
                    localStorage.setItem('vps_session_token', data.token);
                }
                passwordInput.value = '';
                showDashboard();
            } else {
                loginError.textContent = 'Invalid Admin Password';
                loginError.classList.remove('hidden');
            }
        } catch (e) {
            loginError.textContent = 'Connection error to server';
            loginError.classList.remove('hidden');
        }
    });

    logoutBtn.addEventListener('click', async () => {
        await authFetch('/manager/api/auth/logout', { method: 'POST' });
        localStorage.removeItem('vps_session_token');
        showLogin();
    });

    refreshBtn.addEventListener('click', () => {
        fetchServices(true);
        fetchSystemStats();
    });

    // Processes Modal Handlers
    if (viewProcessesBtn) {
        viewProcessesBtn.addEventListener('click', () => {
            processModal.classList.remove('hidden');
            fetchProcessList();
        });
    }

    if (closeProcessModalBtn) {
        closeProcessModalBtn.addEventListener('click', () => {
            processModal.classList.add('hidden');
        });
    }

    if (refreshProcessesBtn) {
        refreshProcessesBtn.addEventListener('click', fetchProcessList);
    }

    if (processSearchInput) {
        processSearchInput.addEventListener('input', renderProcessTable);
    }

    function showLogin() {
        if (metricsInterval) clearInterval(metricsInterval);
        dashboardWrapper.classList.add('hidden');
        loginWrapper.classList.remove('hidden');
    }

    function showDashboard() {
        loginWrapper.classList.add('hidden');
        dashboardWrapper.classList.remove('hidden');
        fetchSystemStats();
        fetchServices(true);
        metricsInterval = setInterval(() => {
            fetchSystemStats();
            fetchServices();
        }, 5000);
    }

    async function fetchSystemStats() {
        try {
            const res = await authFetch('/manager/api/system');
            if (!res.ok) return;
            const data = await res.json();

            // CPU
            document.getElementById('cpu-value').textContent = `${data.cpu_percent}%`;
            document.getElementById('cpu-bar').style.width = `${Math.min(data.cpu_percent, 100)}%`;
            if (data.cpu_details) {
                const coresText = `${data.cpu_details.logical_cores} vCPUs`;
                document.getElementById('cpu-model-text').textContent = `${data.cpu_details.model} (${coresText})`;
                const loads = data.cpu_details.load_avg.join(', ');
                document.getElementById('cpu-load-text').textContent = `Load Avg: ${loads}`;
            }

            // RAM
            const ramPercent = data.memory.percent;
            document.getElementById('ram-value').textContent = `${data.memory.used_mb} / ${data.memory.total_mb} MB`;
            document.getElementById('ram-bar').style.width = `${ramPercent}%`;
            const cacheText = data.memory.cached_mb ? ` | Cache: ${data.memory.cached_mb} MB` : '';
            document.getElementById('ram-avail-text').textContent = `Avail: ${data.memory.available_mb} MB${cacheText}`;

            // Disk
            document.getElementById('disk-value').textContent = `${data.disk.used_gb} / ${data.disk.total_gb} GB`;
            document.getElementById('disk-bar').style.width = `${data.disk.percent}%`;
            document.getElementById('disk-subtext').textContent = `Free: ${data.disk.free_gb} GB (${100 - data.disk.percent}%)`;

            // Swap
            document.getElementById('swap-value').textContent = `${data.swap.used_mb} / ${data.swap.total_mb} MB`;
            document.getElementById('swap-bar').style.width = `${data.swap.percent}%`;
            document.getElementById('swap-subtext').textContent = `Swap Used: ${data.swap.percent}%`;
        } catch (e) {
            console.error(e);
        }
    }

    let currentSortKey = 'ram_mb';
    let currentSortOrder = 'desc';

    document.querySelectorAll('.sortable-th').forEach(th => {
        th.addEventListener('click', () => {
            const key = th.getAttribute('data-sort');
            if (currentSortKey === key) {
                currentSortOrder = currentSortOrder === 'desc' ? 'asc' : 'desc';
            } else {
                currentSortKey = key;
                currentSortOrder = (key === 'name' || key === 'user') ? 'asc' : 'desc';
            }
            updateSortHeaderUI();
            renderProcessTable();
        });
    });

    function updateSortHeaderUI() {
        document.querySelectorAll('.sortable-th').forEach(th => {
            const key = th.getAttribute('data-sort');
            const iconSpan = document.getElementById(`sort-icon-${key}`);
            if (key === currentSortKey) {
                th.classList.add('active-sort');
                if (iconSpan) iconSpan.textContent = currentSortOrder === 'desc' ? '▼' : '▲';
            } else {
                th.classList.remove('active-sort');
                if (iconSpan) iconSpan.textContent = '';
            }
        });
    }

    async function fetchProcessList() {
        try {
            processTableBody.innerHTML = '<tr><td colspan="6" class="text-center">Loading processes...</td></tr>';
            const res = await authFetch('/manager/api/processes');
            if (!res.ok) return;
            runningProcessesData = await res.json();
            renderProcessTable();
        } catch (e) {
            processTableBody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error loading processes</td></tr>';
        }
    }

    function renderProcessTable() {
        const query = (processSearchInput ? processSearchInput.value : '').toLowerCase().trim();
        let filtered = runningProcessesData.filter(p => p.ram_mb > 0 && (
            p.name.toLowerCase().includes(query) || p.user.toLowerCase().includes(query) || String(p.pid).includes(query)
        ));

        filtered.sort((a, b) => {
            let valA = a[currentSortKey];
            let valB = b[currentSortKey];

            if (typeof valA === 'string') valA = valA.toLowerCase();
            if (typeof valB === 'string') valB = valB.toLowerCase();

            if (valA < valB) return currentSortOrder === 'asc' ? -1 : 1;
            if (valA > valB) return currentSortOrder === 'asc' ? 1 : -1;
            return 0;
        });

        if (filtered.length === 0) {
            processTableBody.innerHTML = '<tr><td colspan="6" class="text-center">No active memory-consuming processes found</td></tr>';
            return;
        }

        processTableBody.innerHTML = filtered.map(p => `
            <tr>
                <td><code>${p.pid}</code></td>
                <td><strong>${p.name}</strong></td>
                <td>${p.user}</td>
                <td><span class="badge ${p.cpu_percent > 10 ? 'badge-danger' : 'badge-neutral'}">${p.cpu_percent}%</span></td>
                <td><strong>${p.ram_mb} MB</strong></td>
                <td>${p.ram_percent}%</td>
            </tr>
        `).join('');
    }

    async function fetchServices(showLoader = false) {
        const grid = document.getElementById('services-grid');
        if (showLoader || (grid && grid.children.length === 0)) {
            grid.innerHTML = `
                <div class="services-loader-card glass-card">
                    <div class="spinner"></div>
                    <span>Scanning & Loading Hosted Services...</span>
                </div>
            `;
        }
        try {
            const res = await authFetch('/manager/api/services');
            if (!res.ok) return;
            const services = await res.json();
            renderServices(services);
        } catch (e) {
            console.error(e);
        }
    }

    const inlineTerminalLogs = {};
    const inlineTerminalVisible = {};
    const activeActions = {};

    function scrollTerminalToBottom(box) {
        if (!box) return;
        requestAnimationFrame(() => {
            box.scrollTop = box.scrollHeight;
        });
    }

    function renderServices(services) {
        const grid = document.getElementById('services-grid');
        if (!grid) return;

        grid.innerHTML = '';
        services.forEach(svc => {
            const card = document.createElement('div');
            card.className = 'service-card glass-panel';
            
            const isRunning = svc.status.toLowerCase().startsWith('up');
            const portStr = svc.ports ? svc.ports.split('->')[0] : '';
            const hostPort = portStr.split(':')[1] || portStr;
            const fullUrl = `http://140.238.245.42/9router/`;
            const canVisit = svc.id === '9router';

            const activeAction = activeActions[svc.id];
            const isCardActive = Boolean(activeAction);

            let updateBtnHtml = '';
            if (svc.update_available) {
                const isUpdatingThis = activeAction === 'update';
                updateBtnHtml = `<button type="button" class="btn btn-sm btn-accent action-btn ${isCardActive ? 'disabled-btn' : ''}" data-id="${svc.id}" data-action="update" ${isCardActive ? 'disabled' : ''}>${isUpdatingThis ? '<span class="btn-spinner"></span> UPDATING...' : '⚡ Update'}</button>`;
            }

            const githubHtml = svc.github_url ? `<div><strong style="color:var(--text-primary)">Repository:</strong> <a href="${svc.github_url}" target="_blank" class="service-url-link">🐙 GitHub Repo ↗</a></div>` : '';
            const isTerminalOpen = activeAction || inlineTerminalVisible[svc.id];
            const existingLog = inlineTerminalLogs[svc.id] || '';

            const startBtnHtml = !isRunning ? `<button type="button" class="btn btn-sm btn-primary action-btn ${isCardActive ? 'disabled-btn' : ''}" data-id="${svc.id}" data-action="start" ${isCardActive ? 'disabled' : ''}>${activeAction === 'start' ? '<span class="btn-spinner"></span> STARTING...' : 'Start'}</button>` : '';
            const stopBtnHtml = isRunning ? `<button type="button" class="btn btn-sm btn-danger action-btn ${isCardActive ? 'disabled-btn' : ''}" data-id="${svc.id}" data-action="stop" ${isCardActive ? 'disabled' : ''}>${activeAction === 'stop' ? '<span class="btn-spinner"></span> STOPPING...' : 'Stop'}</button>` : '';
            const restartBtnHtml = `<button type="button" class="btn btn-sm btn-warning action-btn ${isCardActive ? 'disabled-btn' : ''}" data-id="${svc.id}" data-action="restart" ${isCardActive ? 'disabled' : ''}>${activeAction === 'restart' ? '<span class="btn-spinner"></span> RESTARTING...' : 'Restart'}</button>`;
            const logsBtnHtml = `<button type="button" class="btn btn-sm btn-secondary action-btn ${isCardActive ? 'disabled-btn' : ''}" data-id="${svc.id}" data-action="logs" ${isCardActive ? 'disabled' : ''}>${activeAction === 'logs' ? '<span class="btn-spinner"></span> LOGS...' : '📄 Logs'}</button>`;

            card.innerHTML = `
                <div>
                    <div class="service-card-header">
                        <div>
                            <div class="service-name">${svc.name}</div>
                            <div class="service-desc">${svc.description}</div>
                        </div>
                        <span class="badge ${isRunning ? 'badge-accent' : 'btn-outline'}">${svc.status}</span>
                    </div>
                    
                    <div class="service-resource-row">
                        <span class="res-chip">⚡ CPU: ${svc.cpu_usage || '0.0%'}</span>
                        <span class="res-chip">💾 RAM: ${svc.ram_usage || '0 MB'}</span>
                        <span class="res-chip">🔢 PIDs: ${svc.pids || '-'}</span>
                    </div>

                    <div class="service-info-meta">
                        <div><strong style="color:var(--text-primary)">Version:</strong> <code>${svc.version || 'v1.0.0'}</code></div>
                        <div><strong style="color:var(--text-primary)">Ports:</strong> ${svc.ports}</div>
                        <div><strong style="color:var(--text-primary)">URL:</strong> ${canVisit ? `<a href="${fullUrl}" target="_blank" class="service-url-link">${fullUrl} ↗</a>` : '<code>N/A</code>'}</div>
                        ${githubHtml}
                    </div>
                </div>

                <div class="service-actions">
                    <div class="service-actions-primary">
                        ${startBtnHtml}
                        ${stopBtnHtml}
                        ${restartBtnHtml}
                        ${updateBtnHtml}
                    </div>
                    <div class="service-actions-secondary">
                        ${logsBtnHtml}
                    </div>
                </div>

                <!-- Inline Console / Log Panel -->
                <div id="inline-terminal-${svc.id}" class="inline-terminal ${isTerminalOpen ? '' : 'hidden'}">
                    <div class="inline-terminal-header">
                        <span class="terminal-title">Console Output (${svc.name})</span>
                        <div class="terminal-controls">
                            <button type="button" class="btn btn-xs btn-outline copy-log-btn" data-id="${svc.id}">📋 Copy</button>
                            <button type="button" class="btn btn-xs btn-outline clear-log-btn" data-id="${svc.id}">🧹 Clear</button>
                            <button type="button" class="btn btn-xs btn-outline toggle-log-btn" data-id="${svc.id}">▲ Hide</button>
                        </div>
                    </div>
                    <pre id="terminal-box-${svc.id}" class="inline-terminal-box">${existingLog || 'Console output ready...'}</pre>
                </div>
            `;
            grid.appendChild(card);

            const box = document.getElementById(`terminal-box-${svc.id}`);
            if (box && existingLog) {
                scrollTerminalToBottom(box);
            }
        });

        // Event listeners for service action buttons
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetBtn = e.target.closest('.action-btn');
                const id = targetBtn.getAttribute('data-id');
                const action = targetBtn.getAttribute('data-action');
                triggerServiceAction(id, action, targetBtn);
            });
        });

        // Copy log listener
        document.querySelectorAll('.copy-log-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                const text = inlineTerminalLogs[id] || document.getElementById(`terminal-box-${id}`)?.textContent || '';
                navigator.clipboard.writeText(text).then(() => {
                    const orig = e.target.textContent;
                    e.target.textContent = '✓ Copied!';
                    setTimeout(() => e.target.textContent = orig, 2000);
                });
            });
        });

        // Clear log listener
        document.querySelectorAll('.clear-log-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                inlineTerminalLogs[id] = '';
                const box = document.getElementById(`terminal-box-${id}`);
                if (box) box.textContent = 'Console output cleared.';
            });
        });

        // Toggle log listener
        document.querySelectorAll('.toggle-log-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                const term = document.getElementById(`inline-terminal-${id}`);
                if (term) {
                    const isHidden = term.classList.toggle('hidden');
                    inlineTerminalVisible[id] = !isHidden;
                }
            });
        });
    }

    function showToast(type, message) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type} glass-panel`;
        const icon = type === 'success' ? '✓' : '⚠️';
        toast.innerHTML = `<span class="toast-icon">${icon}</span> <span class="toast-msg">${message}</span>`;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-fade-out');
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    }

    async function triggerServiceAction(serviceId, action, clickedBtn) {
        activeActions[serviceId] = action;

        const termElement = document.getElementById(`inline-terminal-${serviceId}`);
        const termBox = document.getElementById(`terminal-box-${serviceId}`);

        if (termElement) termElement.classList.remove('hidden');
        inlineTerminalVisible[serviceId] = true;

        const cardButtons = clickedBtn ? clickedBtn.closest('.service-card')?.querySelectorAll('.action-btn') : [];
        const origBtnHtml = clickedBtn ? clickedBtn.innerHTML : '';

        if (cardButtons) {
            cardButtons.forEach(b => {
                b.disabled = true;
                b.classList.add('disabled-btn');
            });
        }

        if (clickedBtn) {
            clickedBtn.innerHTML = `<span class="btn-spinner"></span> ${action.toUpperCase()}...`;
        }

        const initMsg = `\n[$ Executing ${action.toUpperCase()} for ${serviceId}...]\n`;
        if (termBox) {
            if (!inlineTerminalLogs[serviceId] || action !== 'logs') {
                inlineTerminalLogs[serviceId] = (inlineTerminalLogs[serviceId] || '') + initMsg;
            } else {
                inlineTerminalLogs[serviceId] = initMsg;
            }
            termBox.textContent = inlineTerminalLogs[serviceId];
            scrollTerminalToBottom(termBox);
        }

        let isSuccess = false;
        try {
            const res = await authFetch(`/manager/api/services/${serviceId}/${action}`, {
                method: 'POST'
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                inlineTerminalLogs[serviceId] += chunk;
                if (termBox) {
                    termBox.textContent = inlineTerminalLogs[serviceId];
                    scrollTerminalToBottom(termBox);
                }
            }

            isSuccess = res.ok;
        } catch (e) {
            const errChunk = `\nError executing action: ${e.message}\n`;
            inlineTerminalLogs[serviceId] += errChunk;
            if (termBox) {
                termBox.textContent = inlineTerminalLogs[serviceId];
                scrollTerminalToBottom(termBox);
            }
            isSuccess = false;
        } finally {
            delete activeActions[serviceId];

            if (isSuccess) {
                const actionTitle = action.charAt(0).toUpperCase() + action.slice(1);
                showToast('success', `${serviceId} ${actionTitle} complete!`);
            } else {
                showToast('error', `${serviceId} ${action} failed.`);
            }

            if (cardButtons) {
                cardButtons.forEach(b => {
                    b.disabled = false;
                    b.classList.remove('disabled-btn');
                });
            }
            if (clickedBtn) {
                clickedBtn.innerHTML = origBtnHtml;
            }

            fetchServices();
            fetchSystemStats();
        }
    }
});
