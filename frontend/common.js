const API = '/api';

function getToken() {
    return localStorage.getItem('token');
}

function checkAuth() {
    const token = getToken();
    if (!token) {
        window.location.href = 'login.html';
        return null;
    }
    return token;
}

async function apiGet(endpoint) {
    const res = await fetch(`${API}${endpoint}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    if (res.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

async function apiPost(endpoint, data) {
    const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
        },
        body: JSON.stringify(data)
    });
    if (res.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

async function apiPut(endpoint, data) {
    const res = await fetch(`${API}${endpoint}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
        },
        body: JSON.stringify(data)
    });
    if (res.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

async function apiDelete(endpoint) {
    const res = await fetch(`${API}${endpoint}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    if (res.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = 'login.html';
}

function showMessage(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = `message ${type}`;
    el.textContent = msg;
    const container = document.querySelector('.card') || document.body;
    container.insertBefore(el, container.firstChild);
    setTimeout(() => el.remove(), 5000);
}

function formatDate(d) {
    if (!d) return '-';
    return new Date(d).toLocaleDateString();
}