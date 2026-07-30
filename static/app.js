document.addEventListener('DOMContentLoaded', () => {
    const loginWrapper = document.getElementById('login-container');
    const dashboardWrapper = document.getElementById('dashboard-container');
    const loginForm = document.getElementById('login-form');
    const passwordInput = document.getElementById('password');
    const loginError = document.getElementById('login-error');
    const logoutBtn = document.getElementById('logout-btn');
    const refreshBtn = document.getElementById('refresh-services-btn');
    const vpsHostname = document.getElementById('vps-hostname');

    const logModal = document.getElementById('log-modal');
    const terminalOutput = document.getElementById('terminal-output');
    const modalTitle = document.getElementById('modal-title');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const modalDoneBtn = document.getElementById('modal-done-btn');

    let metricsInterval = null;

    if (vpsHostname) {
        vpsHostname.textContent = window.location.hostname || 'Server Connected';
    }

    // Check existing auth
    checkAuthStatus();

    async function checkAuthStatus() {
        try {
            const res = await fetch('/manager/api/auth/check');
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
        await fetch('/manager/api/auth/logout', { method: 'POST' });
        showLogin();
    });

    refreshBtn.addEventListener('click', () => {
        fetchServices();
        fetchSystemStats();
    });

    closeModalBtn.addEventListener('click', hideModal);
    modalDoneBtn.addEventListener('click', hideModal);

    function showLogin() {
        if (metricsInterval) clearInterval(metricsInterval);
        dashboardWrapper.classList.add('hidden');
        loginWrapper.classList.remove('hidden');
    }

    function showDashboard() {
        loginWrapper.classList.add('hidden');
        dashboardWrapper.classList.remove('hidden');
        fetchSystemStats();
        fetchServices();
        metricsInterval = setInterval(() => {
            fetchSystemStats();
            fetchServices();
        }, 5000);
    }

    async function fetchSystemStats() {
        try {
            const res = await fetch('/manager/api/system');
            if (!res.ok) return;
            const data = await res.json();

            // CPU
            document.getElementById('cpu-value').textContent = `${data.cpu_percent}%`;
            document.getElementById('cpu-bar').style.width = `${Math.min(data.cpu_percent, 100)}%`;

            // RAM
            const ramPercent = data.memory.percent;
            document.getElementById('ram-value').textContent = `${data.memory.used_mb} / ${data.memory.total_mb} MB`;
            document.getElementById('ram-bar').style.width = `${ramPercent}%`;
            document.getElementById('ram-avail-text').textContent = `Available: ${data.memory.available_mb} MB`;

            // Disk
            document.getElementById('disk-value').textContent = `${data.disk.used_gb} / ${data.disk.total_gb} GB`;
            document.getElementById('disk-bar').style.width = `${data.disk.percent}%`;
            document.getElementById('disk-subtext').textContent = `Free: ${data.disk.free_gb} GB`;

            // Swap
            document.getElementById('swap-value').textContent = `${data.swap.used_mb} / ${data.swap.total_mb} MB`;
            document.getElementById('swap-bar').style.width = `${data.swap.percent}%`;
        } catch (e) {
            console.error(e);
        }
    }

    async function fetchServices() {
        try {
            const res = await fetch('/manager/api/services');
            if (!res.ok) return;
            const services = await res.json();
            renderServices(services);
        } catch (e) {
            console.error(e);
        }
    }

    function renderServices(services) {
        const grid = document.getElementById('services-grid');
        grid.innerHTML = '';

        services.forEach(svc => {
            const card = document.createElement('div');
            card.className = 'glass-card service-card';

            const isRunning = svc.status === 'Running';

            card.innerHTML = `
                <div>
                    <div class="service-card-header">
                        <div>
                            <div class="service-name">${svc.name}</div>
                            <div class="service-desc">${svc.description}</div>
                        </div>
                        <span class="badge ${isRunning ? 'badge-accent' : 'btn-outline'}">${svc.status}</span>
                    </div>
                    <div class="service-info-meta">
                        <span><strong style="color:var(--text-primary)">Ports:</strong> ${svc.ports}</span>
                        <span><strong style="color:var(--text-primary)">Route:</strong> <code>${svc.url_path}</code></span>
                    </div>
                </div>
                <div class="service-actions">
                    ${!isRunning ? `<button type="button" class="btn btn-sm btn-primary action-btn" data-id="${svc.id}" data-action="start">Start</button>` : ''}
                    ${isRunning ? `<button type="button" class="btn btn-sm btn-danger action-btn" data-id="${svc.id}" data-action="stop">Stop</button>` : ''}
                    <button type="button" class="btn btn-sm btn-warning action-btn" data-id="${svc.id}" data-action="restart">Restart</button>
                    <button type="button" class="btn btn-sm btn-secondary action-btn" data-id="${svc.id}" data-action="update">🔄 Update</button>
                </div>
            `;
            grid.appendChild(card);
        });

        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                const action = e.target.getAttribute('data-action');
                triggerServiceAction(id, action);
            });
        });
    }

    async function triggerServiceAction(serviceId, action) {
        showModal(`${action.toUpperCase()} ${serviceId}`);
        terminalOutput.textContent = `Initiating ${action} for ${serviceId}...\n`;

        try {
            const res = await fetch(`/manager/api/services/${serviceId}/${action}`, {
                method: 'POST'
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                terminalOutput.textContent += decoder.decode(value);
                terminalOutput.scrollTop = terminalOutput.scrollHeight;
            }

            modalDoneBtn.removeAttribute('disabled');
            modalDoneBtn.textContent = 'Close';
            fetchServices();
            fetchSystemStats();
        } catch (e) {
            terminalOutput.textContent += `\nError executing action: ${e.message}\n`;
            modalDoneBtn.removeAttribute('disabled');
            modalDoneBtn.textContent = 'Close';
        }
    }

    function showModal(title) {
        modalTitle.textContent = title;
        modalDoneBtn.setAttribute('disabled', 'true');
        modalDoneBtn.textContent = 'Executing...';
        logModal.classList.remove('hidden');
    }

    function hideModal() {
        logModal.classList.add('hidden');
    }
});
