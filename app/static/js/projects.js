/**
 * Complete Project Dashboard JavaScript with Manager & Client + Document Upload
 * File: app/static/js/projects.js
 */

const ProjectManager = {
    projects: [],
    filteredProjects: [],
    users: [],
    clients: [],
    currentFilter: 'all',
    currentView: 'grid',
    currentProjectId: null,
    
    // Document upload properties
    selectedFiles: [],
    currentUploadProjectId: null,

    // Initialize
    async init() {
        await Promise.all([
            this.loadUsers(),
            this.loadClients(),
            this.loadProjects(),
            this.loadStats()
        ]);
        this.setupEventListeners();
        this.render();
    },

    // Load users for manager dropdown
    async loadUsers() {
        try {
            const response = await fetch('/api/users', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.users = result.data || result.users || [];
                console.log('Loaded users:', this.users.length);
            }
        } catch (error) {
            console.error('Error loading users:', error);
            this.users = [];
        }
    },

    // Load clients (companies with type 'client')
    async loadClients() {
        try {
            const response = await fetch('/api/companies?type=client', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.clients = result.data || result.companies || [];
                console.log('Loaded clients:', this.clients.length);
            }
        } catch (error) {
            console.error('Error loading clients:', error);
            this.clients = [];
        }
    },

    // Load projects from API
    async loadProjects() {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/projects/', {
                credentials: 'include'
            });
            
            if (!response.ok) throw new Error('Failed to load projects');
            
            const result = await response.json();
            this.projects = result.data || [];
            this.filteredProjects = [...this.projects];
            
            console.log('Loaded projects:', this.projects.length);
            
        } catch (error) {
            console.error('Error loading projects:', error);
            this.showToast('Failed to load projects', 'error');
            this.projects = [];
            this.filteredProjects = [];
        } finally {
            this.showLoading(false);
        }
    },

    // Load statistics
    async loadStats() {
        try {
            const response = await fetch('/api/projects/stats', {
                credentials: 'include'
            });
            
            if (!response.ok) throw new Error('Failed to load stats');
            
            const result = await response.json();
            const stats = result.data;
            
            document.getElementById('totalProjects').textContent = stats.total_projects || this.projects.length;
            document.getElementById('activeProjects').textContent = stats.active_projects || this.projects.filter(p => p.status === 'active').length;
            document.getElementById('completedProjects').textContent = stats.completed_projects || this.projects.filter(p => p.status === 'completed').length;
            document.getElementById('totalContracts').textContent = stats.total_contracts || 0;
            
        } catch (error) {
            console.error('Error loading stats:', error);
            // Fallback to counting from loaded projects
            document.getElementById('totalProjects').textContent = this.projects.length;
            document.getElementById('activeProjects').textContent = this.projects.filter(p => p.status === 'active').length;
            document.getElementById('completedProjects').textContent = this.projects.filter(p => p.status === 'completed').length;
        }
    },
    

    // Populate manager dropdown with search
    populateManagerDropdown() {
        const container = document.getElementById('managerOptions');
        if (!container) return;
        
        container.innerHTML = this.users.map(user => `
            <div class="select-option" onclick="ProjectManager.selectManager('${user.id}', '${user.email}')">
                <div class="option-name">${user.first_name} ${user.last_name}</div>
                <div class="option-email">${user.email}</div>
                <div class="option-role">${user.role || 'User'}</div>
            </div>
        `).join('');
    },

    // Populate client dropdown with search
    populateClientDropdown() {
        const container = document.getElementById('clientOptions');
        if (!container) return;
        
        container.innerHTML = this.clients.map(client => `
            <div class="select-option" onclick="ProjectManager.selectClient('${client.id}', '${client.company_name}')">
                <div class="option-name">${client.company_name}</div>
                <div class="option-email">${client.email || 'N/A'}</div>
            </div>
        `).join('');
    },

    // Select manager
    selectManager(userId, email) {
        document.getElementById('projectManager').value = userId;
        document.getElementById('managerDisplay').innerHTML = `
            <span>${email}</span>
            <i class="ti ti-chevron-down"></i>
        `;
        this.toggleDropdown('managerDropdown');
    },

    // Select client
    selectClient(clientId, name) {
        document.getElementById('projectClient').value = clientId;
        document.getElementById('clientDisplay').innerHTML = `
            <span>${name}</span>
            <i class="ti ti-chevron-down"></i>
        `;
        this.toggleDropdown('clientDropdown');
    },

    // Filter managers
    filterManagers(query) {
        const searchTerm = query.toLowerCase();
        const container = document.getElementById('managerOptions');
        
        const filtered = this.users.filter(user => 
            user.first_name.toLowerCase().includes(searchTerm) ||
            user.last_name.toLowerCase().includes(searchTerm) ||
            user.email.toLowerCase().includes(searchTerm)
        );
        
        container.innerHTML = filtered.map(user => `
            <div class="select-option" onclick="ProjectManager.selectManager('${user.id}', '${user.email}')">
                <div class="option-name">${user.first_name} ${user.last_name}</div>
                <div class="option-email">${user.email}</div>
                <div class="option-role">${user.role || 'User'}</div>
            </div>
        `).join('');
        
        if (filtered.length === 0) {
            container.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-muted);">No managers found</div>';
        }
    },

    // Filter clients
    filterClients(query) {
        const searchTerm = query.toLowerCase();
        const container = document.getElementById('clientOptions');
        
        const filtered = this.clients.filter(client => 
            client.company_name.toLowerCase().includes(searchTerm) ||
            (client.email && client.email.toLowerCase().includes(searchTerm))
        );
        
        container.innerHTML = filtered.map(client => `
            <div class="select-option" onclick="ProjectManager.selectClient('${client.id}', '${client.company_name}')">
                <div class="option-name">${client.company_name}</div>
                <div class="option-email">${client.email || 'N/A'}</div>
            </div>
        `).join('');
        
        if (filtered.length === 0) {
            container.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-muted);">No clients found</div>';
        }
    },

    // Toggle dropdown
    toggleDropdown(dropdownId) {
        const dropdown = document.getElementById(dropdownId);
        const isShowing = dropdown.classList.contains('show');
        
        // Close all dropdowns
        document.querySelectorAll('.select-dropdown').forEach(d => d.classList.remove('show'));
        
        if (!isShowing) {
            dropdown.classList.add('show');
            
            // Populate dropdowns when opened
            if (dropdownId === 'managerDropdown') {
                this.populateManagerDropdown();
            } else if (dropdownId === 'clientDropdown') {
                this.populateClientDropdown();
            }
        }
    },

    // Get manager name by ID
    getManagerName(managerId) {
        if (!managerId) return 'Not Assigned';
        const manager = this.users.find(u => u.id === managerId);
        return manager ? `${manager.first_name} ${manager.last_name}` : 'Unknown';
    },

    // Get client name by ID
    getClientName(clientId) {
        if (!clientId) return 'N/A';
        const client = this.clients.find(c => c.id === clientId);
        return client ? client.company_name : 'Unknown';
    },

    // Render projects
    render() {
        if (this.currentView === 'grid') {
            this.renderGrid();
        } else {
            this.renderTable();
        }
        document.getElementById('projectCount').textContent = this.filteredProjects.length;
    },

    // Render grid view - UPDATED with fixed menu icon
    renderGrid() {
        const grid = document.getElementById('projectsGrid');
        
        if (this.filteredProjects.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <i class="ti ti-folder-off"></i>
                    <h3>No projects found</h3>
                    <p>Create your first project to get started</p>
                    <br>
                    <button class="btn btn-primary" onclick="ProjectManager.openCreateModal()">
                        <i class="ti ti-plus"></i> Create Project
                    </button>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.filteredProjects.map(project => `
            <div class="project-card" onclick="ProjectManager.viewProject('${project.id}')">
                <button class="project-menu-btn" onclick="event.stopPropagation(); ProjectManager.showProjectMenu(event, '${project.id}')">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="1"></circle>
                        <circle cx="12" cy="5" r="1"></circle>
                        <circle cx="12" cy="19" r="1"></circle>
                    </svg>
                </button>
                <div class="project-header">
                    <div class="project-title-row">
                        <div>
                            <div class="project-code">${project.project_code || project.code || ''}</div>
                            <h3 class="project-title">${project.project_name || project.title || 'Untitled Project'}</h3>
                        </div>
                    </div>
                    <div class="project-meta">
                        <div class="meta-item">
                            <i class="ti ti-user"></i>
                            <span>${this.getManagerName(project.project_manager_id)}</span>
                        </div>
                        <div class="meta-item">
                            <i class="ti ti-building"></i>
                            <span>${this.getClientName(project.client_id)}</span>
                        </div>
                        <div class="meta-item">
                            <i class="ti ti-calendar"></i>
                            <span>${this.formatDate(project.start_date || project.startDate)}</span>
                        </div>
                        <div class="meta-item">
                            <i class="ti ti-currency-dollar"></i>
                            <span>${this.formatCurrency(project.project_value || project.value || 0)}</span>
                        </div>
                    </div>
                </div>
               
            </div>
        `).join('');
    },

    // Render table view
    renderTable() {
        const tbody = document.getElementById('tableBody');
        
        if (this.filteredProjects.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="empty-state">
                        <i class="ti ti-folder-off"></i>
                        <h3>No projects found</h3>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.filteredProjects.map(project => `
            <tr onclick="ProjectManager.viewProject('${project.id}')" style="cursor: pointer;">
                <td>
                    <div style="font-weight: 600;">${project.project_name || project.title}</div>
                    <small style="color: var(--text-muted); font-size: 0.813rem;">${project.project_code || project.code}</small>
                </td>
                <td><span class="status-badge ${project.status || 'planning'}">${(project.status || 'planning').replace('-', ' ').toUpperCase()}</span></td>
                <td>${this.getManagerName(project.project_manager_id)}</td>
                <td>${this.getClientName(project.client_id)}</td>
                <td>${this.formatDate(project.start_date || project.startDate)}</td>
                <td>${this.formatCurrency(project.project_value || project.value || 0)}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div class="progress-bar" style="width: 100px;">
                            <div class="progress-fill" style="width: ${project.progress || 0}%"></div>
                        </div>
                        <span style="font-size: 0.813rem; color: var(--text-muted);">${project.progress || 0}%</span>
                    </div>
                </td>
                <td onclick="event.stopPropagation();">
                    <button class="btn btn-sm" onclick="ProjectManager.openEditModal('${project.id}')" title="Edit">
                        <i class="ti ti-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="ProjectManager.deleteProject('${project.id}')" title="Delete">
                        <i class="ti ti-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    },

    // Open create modal
    openCreateModal() {
        document.getElementById('modalTitle').textContent = 'Create New Project';
        document.getElementById('projectForm').reset();
        document.getElementById('projectId').value = '';
        document.getElementById('projectCode').value = this.generateProjectCode();
        
        // Reset dropdowns
        document.getElementById('managerDisplay').innerHTML = '<span>Select Manager by Email</span><i class="ti ti-chevron-down"></i>';
        document.getElementById('clientDisplay').innerHTML = '<span>Select Client by Email</span><i class="ti ti-chevron-down"></i>';
        
        this.openModal('projectModal');
    },

    // Open edit modal - FIXED
    async openEditModal(projectId) {
        try {
            const numericProjectId = parseInt(projectId, 10);
            console.log('Opening edit modal for project:', numericProjectId);
            
            const project = this.projects.find(p => parseInt(p.id) === numericProjectId);
            
            if (!project) {
                console.error('Project not found in local array:', numericProjectId);
                this.showToast('Project not found', 'error');
                return;
            }

            document.getElementById('modalTitle').textContent = 'Edit Project';
            document.getElementById('projectId').value = numericProjectId;
            document.getElementById('projectTitle').value = project.project_name || project.title || '';
            document.getElementById('projectCode').value = project.project_code || project.code || '';
            document.getElementById('projectStatus').value = project.status || 'planning';
            document.getElementById('projectStartDate').value = project.start_date || project.startDate || '';
            document.getElementById('projectEndDate').value = project.end_date || project.endDate || '';
            document.getElementById('projectValue').value = project.project_value || project.value || 0;
            document.getElementById('projectDescription').value = project.description || '';
            
            const managerId = project.project_manager_id;
            if (managerId && this.users.length > 0) {
                const manager = this.users.find(u => parseInt(u.id) === parseInt(managerId));
                if (manager) {
                    document.getElementById('projectManager').value = managerId;
                    const managerName = `${manager.first_name || ''} ${manager.last_name || ''}`.trim() || manager.email || manager.username;
                    document.getElementById('managerDisplay').innerHTML = `<span>${managerName}</span><i class="ti ti-chevron-down"></i>`;
                }
            } else {
                document.getElementById('managerDisplay').innerHTML = `<span>Select Manager</span><i class="ti ti-chevron-down"></i>`;
            }
            
            const clientId = project.client_id;
            if (clientId && this.clients.length > 0) {
                const client = this.clients.find(c => parseInt(c.id) === parseInt(clientId));
                if (client) {
                    document.getElementById('projectClient').value = clientId;
                    document.getElementById('clientDisplay').innerHTML = `<span>${client.company_name}</span><i class="ti ti-chevron-down"></i>`;
                }
            } else {
                document.getElementById('clientDisplay').innerHTML = `<span>Select Client</span><i class="ti ti-chevron-down"></i>`;
            }
            
            this.openModal('projectModal');
            
        } catch (error) {
            console.error('Error opening edit modal:', error);
            this.showToast('Failed to load project details', 'error');
        }
    },

    // Save project
    async saveProject() {
        try {
            const projectId = document.getElementById('projectId').value;
            
            const projectData = {
                title: document.getElementById('projectTitle').value,
                code: document.getElementById('projectCode').value,
                status: document.getElementById('projectStatus').value,
                start_date: document.getElementById('projectStartDate').value || null,
                end_date: document.getElementById('projectEndDate').value || null,
                value: parseFloat(document.getElementById('projectValue').value) || 0,
                description: document.getElementById('projectDescription').value,
                project_manager_id: document.getElementById('projectManager').value || null,
                client_id: document.getElementById('projectClient').value || null
            };

            if (!projectData.title || !projectData.code) {
                this.showToast('Please fill in all required fields', 'error');
                return;
            }

            if (!projectData.project_manager_id) {
                this.showToast('Please select a project manager', 'error');
                return;
            }

            if (!projectData.client_id) {
                this.showToast('Please select a client', 'error');
                return;
            }

            this.showLoading(true);

            const url = projectId ? `/api/projects/${projectId}` : '/api/projects/';
            const method = projectId ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(projectData)
            });

            const result = await response.json();

            if (result.success) {
                this.showToast(projectId ? 'Project updated successfully!' : 'Project created successfully!', 'success');
                this.closeModal('projectModal');
                await this.loadProjects();
                await this.loadStats();
                this.render();
            } else {
                throw new Error(result.message || 'Failed to save project');
            }

        } catch (error) {
            console.error('Error saving project:', error);
            this.showToast(error.message || 'Failed to save project', 'error');
        } finally {
            this.showLoading(false);
        }
    },

    // Delete project
    async deleteProject(projectId) {
        if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
            return;
        }

        try {
            this.showLoading(true);

            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE',
                credentials: 'include'
            });

            const result = await response.json();

            if (result.success) {
                this.showToast('Project deleted successfully!', 'success');
                await this.loadProjects();
                await this.loadStats();
                this.render();
            } else {
                throw new Error(result.message || 'Failed to delete project');
            }

        } catch (error) {
            console.error('Error deleting project:', error);
            this.showToast(error.message || 'Failed to delete project', 'error');
        } finally {
            this.showLoading(false);
        }
    },

    // View project
    viewProject(projectId) {
        try {
            const numericProjectId = parseInt(projectId, 10);
            console.log('📖 Opening view modal for project:', numericProjectId);
            
            const project = this.projects.find(p => parseInt(p.id) === numericProjectId);
            
            if (!project) {
                console.error('Project not found:', numericProjectId);
                this.showToast('Project not found', 'error');
                return;
            }

            this.currentProjectId = numericProjectId;
            
            const modalBody = document.getElementById('viewModalBody');
            modalBody.innerHTML = `
                <div style="display: grid; gap: 2rem;">
                    <div>
                        <h2 style="margin: 0 0 1rem 0; color: var(--text-color);">
                            ${project.project_name || project.title || 'Untitled Project'}
                        </h2>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem;">
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">Project Code:</strong>
                                <div style="margin-top: 0.25rem;">${project.project_code || project.code || 'N/A'}</div>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">Status:</strong>
                                <div style="margin-top: 0.25rem;">
                                    <span class="status-badge ${project.status || 'planning'}">
                                        ${(project.status || 'planning').replace('-', ' ').toUpperCase()}
                                    </span>
                                </div>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">Project Manager:</strong>
                                <div style="margin-top: 0.25rem;">${this.getManagerName(project.project_manager_id)}</div>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">Client:</strong>
                                <div style="margin-top: 0.25rem;">${this.getClientName(project.client_id)}</div>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">Start Date:</strong>
                                <div style="margin-top: 0.25rem;">${this.formatDate(project.start_date || project.startDate)}</div>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">End Date:</strong>
                                <div style="margin-top: 0.25rem;">
                                    ${project.end_date || project.endDate ? this.formatDate(project.end_date || project.endDate) : 'Not set'}
                                </div>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">Project Value:</strong>
                                <div style="margin-top: 0.25rem; font-weight: 600; color: var(--primary-color);">
                                    ${this.formatCurrency(project.project_value || project.value || 0)}
                                </div>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted); font-size: 0.875rem;">Progress:</strong>
                                <div style="margin-top: 0.25rem;">${project.progress || 0}%</div>
                            </div>
                        </div>
                    </div>
                  
                    <div style="padding-top: 1rem; border-top: 1px solid var(--border-color);">
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; font-size: 0.875rem;">
                            <div>
                                <strong style="color: var(--text-muted);">Created:</strong>
                                <span style="color: var(--text-color);">${this.formatDate(project.created_at || project.createdDate)}</span>
                            </div>
                            <div>
                                <strong style="color: var(--text-muted);">Last Updated:</strong>
                                <span style="color: var(--text-color);">${this.formatDate(project.updated_at || project.updatedDate)}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.getElementById('viewModalTitle').textContent = project.project_name || project.title || 'Project Details';
            this.openModal('viewModal');
            
        } catch (error) {
            console.error('Error in viewProject:', error);
            this.showToast('Failed to display project details', 'error');
        }
    },

    // Edit from view
    editFromView() {
        this.closeModal('viewModal');
        this.openEditModal(this.currentProjectId);
    },

    // Search projects
    search(query) {
        const searchTerm = query.toLowerCase();
        if (!searchTerm) {
            this.filteredProjects = [...this.projects];
        } else {
            this.filteredProjects = this.projects.filter(p => {
                const managerName = this.getManagerName(p.project_manager_id).toLowerCase();
                const clientName = this.getClientName(p.client_id).toLowerCase();
                
                return (p.project_name || p.title || '').toLowerCase().includes(searchTerm) ||
                       (p.project_code || p.code || '').toLowerCase().includes(searchTerm) ||
                       (p.description || '').toLowerCase().includes(searchTerm) ||
                       managerName.includes(searchTerm) ||
                       clientName.includes(searchTerm);
            });
        }
        this.render();
    },

    // Filter projects
    filter(status) {
        this.currentFilter = status;
        
        document.querySelectorAll('#filterMenu .dropdown-item').forEach(item => {
            item.classList.remove('active');
        });
        event.target.classList.add('active');

        if (status === 'all') {
            this.filteredProjects = [...this.projects];
        } else {
            this.filteredProjects = this.projects.filter(p => p.status === status);
        }
        
        this.render();
        this.toggleFilter();
    },

    // Toggle filter dropdown
    toggleFilter() {
        const menu = document.getElementById('filterMenu');
        menu.classList.toggle('show');
    },

    // Switch view
    switchView(view) {
        this.currentView = view;
        
        document.querySelectorAll('.view-toggle button').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.closest('button').classList.add('active');

        const grid = document.getElementById('projectsGrid');
        const table = document.getElementById('projectsTable');
        
        if (view === 'grid') {
            grid.style.display = 'grid';
            table.classList.remove('show');
        } else {
            grid.style.display = 'none';
            table.classList.add('show');
        }
        
        this.render();
    },

    // Show project menu - UPDATED with document upload options
    showProjectMenu(event, projectId) {
        event.stopPropagation();
        
        // Remove existing menus
        document.querySelectorAll('.project-context-menu').forEach(m => m.remove());
        
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu show project-context-menu';
        menu.style.position = 'fixed';
        menu.style.zIndex = '10000';
        
        const rect = event.target.getBoundingClientRect();
        menu.style.top = `${rect.bottom + 5}px`;
        menu.style.right = `${window.innerWidth - rect.right}px`;
        
        menu.innerHTML = `
            <button class="dropdown-item" onclick="ProjectManager.viewProject('${projectId}')">
                <i class="ti ti-eye"></i> View Details
            </button>
            <button class="dropdown-item" onclick="ProjectManager.openUploadModal('${projectId}')">
                <i class="ti ti-upload"></i> Upload Documents
            </button>
            <button class="dropdown-item" onclick="ProjectManager.viewProjectDocuments('${projectId}')">
                <i class="ti ti-files"></i> View Documents
            </button>
            <div style="height: 1px; background: var(--border-color); margin: 0.25rem 0;"></div>
            <button class="dropdown-item" onclick="ProjectManager.openEditModal('${projectId}')">
                <i class="ti ti-edit"></i> Edit Project
            </button>
            <button class="dropdown-item" onclick="ProjectManager.deleteProject('${projectId}')">
                <i class="ti ti-trash"></i> Delete
            </button>
        `;
        
        document.body.appendChild(menu);
        
        setTimeout(() => {
            const closeMenu = (e) => {
                if (!menu.contains(e.target)) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            };
            document.addEventListener('click', closeMenu);
        }, 0);
    },

    // =================================================
    // DOCUMENT UPLOAD FUNCTIONS
    // =================================================

    openUploadModal(projectId) {
        const project = this.projects.find(p => p.id == projectId);
        if (!project) {
            this.showToast('Project not found', 'error');
            return;
        }
        
        this.currentUploadProjectId = projectId;
        this.selectedFiles = [];
        
        document.getElementById('uploadProjectName').textContent = project.project_name || project.title;
        document.getElementById('projectFileInput').value = '';
        document.getElementById('uploadNotes').value = '';
        document.getElementById('selectedFilesList').style.display = 'none';
        document.getElementById('filesContainer').innerHTML = '';
        document.getElementById('fileCount').textContent = '0';
        document.getElementById('uploadButton').disabled = true;
        document.getElementById('uploadProgress').style.display = 'none';
        
        this.openModal('uploadDocumentsModal');
        this.setupUploadEventListeners();
    },

    setupUploadEventListeners() {
        const dropZone = document.getElementById('fileDropZone');
        const fileInput = document.getElementById('projectFileInput');
        
        dropZone.onclick = (e) => {
            if (e.target.tagName !== 'BUTTON') {
                fileInput.click();
            }
        };
        
        fileInput.onchange = (e) => {
            this.handleFileSelect(e.target.files);
        };
        
        dropZone.ondragover = (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        };
        
        dropZone.ondragleave = () => {
            dropZone.classList.remove('drag-over');
        };
        
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            this.handleFileSelect(e.dataTransfer.files);
        };
    },

    handleFileSelect(files) {
        const allowedExtensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'rtf', 'odt', 'eml'];
        const maxSize = 50 * 1024 * 1024;
        
        Array.from(files).forEach(file => {
            const ext = file.name.split('.').pop().toLowerCase();
            
            if (!allowedExtensions.includes(ext)) {
                this.showToast(`${file.name}: File type not allowed`, 'error');
                return;
            }
            
            if (file.size > maxSize) {
                this.showToast(`${file.name}: File size exceeds 50MB`, 'error');
                return;
            }
            
            if (this.selectedFiles.find(f => f.name === file.name)) {
                this.showToast(`${file.name}: Already added`, 'warning');
                return;
            }
            
            this.selectedFiles.push(file);
        });
        
        this.renderSelectedFiles();
    },

    renderSelectedFiles() {
        const container = document.getElementById('filesContainer');
        const filesList = document.getElementById('selectedFilesList');
        const fileCount = document.getElementById('fileCount');
        const uploadButton = document.getElementById('uploadButton');
        
        if (this.selectedFiles.length === 0) {
            filesList.style.display = 'none';
            uploadButton.disabled = true;
            return;
        }
        
        filesList.style.display = 'block';
        fileCount.textContent = this.selectedFiles.length;
        uploadButton.disabled = false;
        
        container.innerHTML = this.selectedFiles.map((file, index) => {
            const sizeStr = this.formatFileSize(file.size);
            const icon = this.getFileIcon(file.name);
            
            return `
                <div class="file-item">
                    <div class="file-item-info">
                        <i class="ti ${icon} file-item-icon"></i>
                        <div class="file-item-details">
                            <div class="file-item-name">${file.name}</div>
                            <div class="file-item-size">${sizeStr}</div>
                        </div>
                    </div>
                    <button class="file-item-remove" onclick="ProjectManager.removeFile(${index})" title="Remove">
                        <i class="ti ti-x"></i>
                    </button>
                </div>
            `;
        }).join('');
    },

    removeFile(index) {
        this.selectedFiles.splice(index, 1);
        this.renderSelectedFiles();
    },

    async uploadDocuments() {
        if (this.selectedFiles.length === 0) {
            this.showToast('Please select files to upload', 'error');
            return;
        }
        
        const uploadButton = document.getElementById('uploadButton');
        const uploadProgress = document.getElementById('uploadProgress');
        const progressBar = document.getElementById('uploadProgressBar');
        const uploadStatus = document.getElementById('uploadStatus');
        
        try {
            uploadButton.disabled = true;
            uploadProgress.style.display = 'block';
            progressBar.style.width = '0%';
            uploadStatus.textContent = 'Preparing upload...';
            
            const formData = new FormData();
            this.selectedFiles.forEach(file => {
                formData.append('files', file);
            });
            
            const notes = document.getElementById('uploadNotes').value;
            if (notes) {
                formData.append('notes', notes);
            }
            
            formData.append('document_type', 'project_document');
            
            progressBar.style.width = '50%';
            uploadStatus.textContent = `Uploading ${this.selectedFiles.length} file(s)...`;
            
            const response = await fetch(`/api/projects/${this.currentUploadProjectId}/documents/upload`, {
                method: 'POST',
                credentials: 'include',
                body: formData
            });
            
            progressBar.style.width = '100%';
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
            }
            
            const result = await response.json();
            uploadStatus.textContent = 'Upload complete!';
            
            const uploadedCount = result.data?.uploaded?.length || 0;
            const errorCount = result.data?.errors?.length || 0;
            
            if (uploadedCount > 0) {
                this.showToast(`Successfully uploaded ${uploadedCount} document(s)`, 'success');
            }
            
            if (errorCount > 0) {
                this.showToast(`${errorCount} file(s) failed to upload`, 'error');
            }
            
            setTimeout(() => {
                this.closeModal('uploadDocumentsModal');
                this.viewProjectDocuments(this.currentUploadProjectId);
            }, 1500);
            
        } catch (error) {
            console.error('Upload error:', error);
            this.showToast(error.message || 'Upload failed', 'error');
            uploadButton.disabled = false;
            uploadProgress.style.display = 'none';
        }
    },

    async viewProjectDocuments(projectId) {
        const project = this.projects.find(p => p.id == projectId);
        if (!project) {
            this.showToast('Project not found', 'error');
            return;
        }
        
        this.currentUploadProjectId = projectId;
        document.getElementById('docProjectName').textContent = project.project_name || project.title;
        this.openModal('viewDocumentsModal');
        
        await this.loadProjectDocuments(projectId);
    },

    async loadProjectDocuments(projectId) {
        const tbody = document.getElementById('documentsTableBody');
        
        try {
            const response = await fetch(`/api/projects/${projectId}/documents`, {
                credentials: 'include'
            });
            
            if (!response.ok) throw new Error('Failed to load documents');
            
            const result = await response.json();
            const documents = result.data || [];
            
            if (documents.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">
                            <i class="ti ti-folder-off" style="font-size: 2rem; margin-bottom: 0.5rem;"></i>
                            <p>No documents uploaded yet</p>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = documents.map(doc => `
                <tr>
                    <td>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <i class="ti ${this.getFileIcon(doc.name)}" style="color: var(--primary-color);"></i>
                            <span>${doc.name}</span>
                        </div>
                    </td>
                    <td>${doc.type || 'Unknown'}</td>
                    <td>${doc.size || 'Unknown'}</td>
                    <td>${doc.uploaded_by_name || 'Unknown'}</td>
                    <td>${doc.uploadedAt ? new Date(doc.uploadedAt).toLocaleDateString() : 'Unknown'}</td>
                    <td>
                        <div class="doc-actions">
                            <button class="doc-action-btn" onclick="ProjectManager.downloadDocument('${doc.id}')" title="Download">
                                <i class="ti ti-download"></i>
                            </button>
                            <button class="doc-action-btn" onclick="ProjectManager.deleteDocument('${doc.id}', '${projectId}')" title="Delete" style="color: var(--danger-color, #ef4444);">
                                <i class="ti ti-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
            
        } catch (error) {
            console.error('Error loading documents:', error);
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 2rem; color: var(--danger-color, #ef4444);">
                        <i class="ti ti-alert-circle" style="font-size: 2rem; margin-bottom: 0.5rem;"></i>
                        <p>Failed to load documents</p>
                    </td>
                </tr>
            `;
        }
    },

    closeDocumentsModal() {
        this.closeModal('viewDocumentsModal');
    },

    openUploadModalFromDocs() {
        this.closeDocumentsModal();
        this.openUploadModal(this.currentUploadProjectId);
    },

    downloadDocument(documentId) {
        window.open(`/api/documents/${documentId}/download`, '_blank');
    },

    async deleteDocument(documentId, projectId) {
        if (!confirm('Are you sure you want to delete this document?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/documents/${documentId}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            
            if (!response.ok) throw new Error('Delete failed');
            
            this.showToast('Document deleted successfully', 'success');
            await this.loadProjectDocuments(projectId);
            
        } catch (error) {
            console.error('Delete error:', error);
            this.showToast('Failed to delete document', 'error');
        }
    },

    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const iconMap = {
            'pdf': 'ti-file-type-pdf',
            'doc': 'ti-file-type-doc',
            'docx': 'ti-file-type-docx',
            'xls': 'ti-file-type-xls',
            'xlsx': 'ti-file-type-xlsx',
            'txt': 'ti-file-text',
            'rtf': 'ti-file-text',
            'odt': 'ti-file-text',
            'eml': 'ti-mail'
        };
        return iconMap[ext] || 'ti-file';
    },

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    },

    // =================================================
    // END DOCUMENT UPLOAD FUNCTIONS
    // =================================================

    // Export/Import (placeholder)
    exportData() {
        this.showToast('Export functionality coming soon', 'info');
    },

    importData() {
        this.showToast('Import functionality coming soon', 'info');
    },

    // Modal functions
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
    },

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');
        document.body.style.overflow = '';
    },

    // Utility functions
    generateProjectCode() {
        const date = new Date();
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
        return `PROJ-${year}-${month}-${random}`;
    },

    formatCurrency(value) {
        return new Intl.NumberFormat('en-QA', {
            style: 'currency',
            currency: 'QAR',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value || 0);
    },

    formatDate(date) {
        if (!date) return 'Not set';
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        }).format(new Date(date));
    },

    showLoading(show) {
        let overlay = document.getElementById('loadingOverlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'loadingOverlay';
            overlay.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; gap: 1rem;">
                    <div class="spinner"></div>
                    <div style="color: white; font-weight: 500;">Loading...</div>
                </div>
            `;
            overlay.style.cssText = `
                display: none;
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.7);
                z-index: 10000;
                align-items: center;
                justify-content: center;
            `;
            document.body.appendChild(overlay);
        }
        overlay.style.display = show ? 'flex' : 'none';
    },

    showToast(message, type = 'info') {
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="ti ti-${type === 'success' ? 'check' : type === 'error' ? 'x' : type === 'warning' ? 'alert-triangle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    setupEventListeners() {
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown') && !e.target.closest('.searchable-select')) {
                document.querySelectorAll('.dropdown-menu, .select-dropdown').forEach(menu => {
                    menu.classList.remove('show');
                });
            }
        });

        // document.addEventListener('keydown', (e) => {
        //     if (e.key === 'Escape') {
        //         ['projectModal', 'viewModal', 'uploadDocumentsModal', 'viewDocumentsModal'].forEach(modalId => {
        //             const modal = document.getElementById(modalId);
        //             if (modal && modal.classList.contains('show')) {
        //                 this.closeModal(modalId);
        //             }
        //         });
        //     }
        // });

        ['projectModal', 'viewModal', 'uploadDocumentsModal', 'viewDocumentsModal'].forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        this.closeModal(modalId);
                    }
                });
            }
        });
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    ProjectManager.init();
});