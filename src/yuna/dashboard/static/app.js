document.addEventListener('DOMContentLoaded', () => {
    // Navigation Logic
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.view-section');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Update active nav
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Show corresponding section
            const targetView = item.getAttribute('data-view');
            sections.forEach(sec => {
                sec.classList.remove('active');
                if (sec.id === targetView) sec.classList.add('active');
            });

            // Load data if needed
            if (targetView === 'memory-view') loadMemories();
            if (targetView === 'prompt-view') loadPrompt();
        });
    });

    // --- MEMORY SYSTEM ---
    let allMemories = [];

    async function loadMemories() {
        const container = document.getElementById('memory-container');
        container.innerHTML = '<div class="loading-state">Loading neural pathways...</div>';
        
        try {
            const res = await fetch('/api/memories');
            const data = await res.json();
            allMemories = data.memories || [];
            renderMemories();
        } catch (e) {
            container.innerHTML = `<div class="loading-state" style="color: var(--danger)">Failed to load memories: ${e.message}</div>`;
        }
    }

    function renderMemories() {
        const container = document.getElementById('memory-container');
        const filterText = document.getElementById('memory-search').value.toLowerCase();
        const filterPartition = document.getElementById('partition-filter').value;

        container.innerHTML = '';

        let filtered = allMemories.filter(m => {
            const matchesText = m.fact.toLowerCase().includes(filterText) || m.username.toLowerCase().includes(filterText);
            const isGlobal = m.username === 'global';
            const matchesPartition = filterPartition === 'all' || 
                                     (filterPartition === 'global' && isGlobal) || 
                                     (filterPartition === 'personal' && !isGlobal);
            return matchesText && matchesPartition;
        });

        if (filtered.length === 0) {
            container.innerHTML = '<div class="loading-state">No matching memories found.</div>';
            return;
        }

        filtered.forEach(m => {
            const isGlobal = m.username === 'global';
            const partitionClass = isGlobal ? 'global' : 'personal';
            const partitionName = isGlobal ? 'GLOBAL' : `USER:${m.username}`;
            
            const el = document.createElement('div');
            el.className = 'memory-item';
            el.innerHTML = `
                <div class="memory-partition">
                    <div class="dot ${partitionClass}"></div>
                    <span style="font-size: 12px; font-weight: 600; color: ${isGlobal ? 'var(--accent-secondary)' : 'var(--accent-primary)'}">${partitionName}</span>
                </div>
                <div class="memory-fact">${m.fact}</div>
                <div class="memory-id">${m.id}</div>
                <div class="col-actions">
                    <button class="action-btn delete-btn" data-id="${m.id}" title="Delete Fact"><i class="fa-solid fa-trash"></i></button>
                </div>
            `;
            container.appendChild(el);
        });

        // Attach delete listeners
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const id = e.currentTarget.getAttribute('data-id');
                if (confirm('Are you sure you want to permanently delete this neural pathway?')) {
                    await deleteMemory(id);
                }
            });
        });
    }

    document.getElementById('memory-search').addEventListener('input', renderMemories);
    document.getElementById('partition-filter').addEventListener('change', renderMemories);

    async function deleteMemory(id) {
        try {
            const res = await fetch(`/api/memories/${id}`, { method: 'DELETE' });
            if (res.ok) {
                allMemories = allMemories.filter(m => m.id !== id);
                renderMemories();
            } else {
                alert("Failed to delete memory.");
            }
        } catch (e) {
            console.error(e);
        }
    }

    // Modal Logic
    const modal = document.getElementById('add-memory-modal');
    document.getElementById('btn-add-memory').addEventListener('click', () => {
        modal.classList.add('active');
        document.getElementById('new-memory-fact').value = '';
    });
    
    document.getElementById('btn-cancel-memory').addEventListener('click', () => {
        modal.classList.remove('active');
    });

    document.getElementById('btn-submit-memory').addEventListener('click', async () => {
        const username = document.getElementById('new-memory-username').value.trim();
        const fact = document.getElementById('new-memory-fact').value.trim();
        if (!username || !fact) return alert("Please fill out all fields.");

        try {
            const res = await fetch('/api/memories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, fact })
            });
            if (res.ok) {
                modal.classList.remove('active');
                loadMemories();
            } else {
                alert("Failed to add memory.");
            }
        } catch (e) {
            console.error(e);
        }
    });

    // --- PROMPT SYSTEM ---
    async function loadPrompt() {
        const editor = document.getElementById('prompt-editor');
        editor.value = 'Loading core protocols...';
        try {
            const res = await fetch('/api/prompt');
            const data = await res.json();
            editor.value = data.content;
        } catch (e) {
            editor.value = `Error loading prompt: ${e.message}`;
        }
    }

    document.getElementById('btn-save-prompt').addEventListener('click', async () => {
        const btn = document.getElementById('btn-save-prompt');
        const content = document.getElementById('prompt-editor').value;
        const oldText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        
        try {
            const res = await fetch('/api/prompt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });
            if (res.ok) {
                btn.innerHTML = '<i class="fa-solid fa-check"></i> Saved';
                setTimeout(() => btn.innerHTML = oldText, 2000);
            }
        } catch (e) {
            alert('Failed to save prompt.');
            btn.innerHTML = oldText;
        }
    });

    // Initialize
    loadMemories();
});
