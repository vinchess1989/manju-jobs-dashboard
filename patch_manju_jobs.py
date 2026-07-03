import os
import re

INDEX_PATH = r"c:\Users\vinee\manju_jobs\firebase_app\index.html"
SCRAPER_PATH = r"c:\Users\vinee\manju_jobs\scraper.py"

# 1. Update scraper.py
with open(SCRAPER_PATH, 'r', encoding='utf-8') as f:
    scraper_code = f.read()

# Add handling for applied_update
applied_update_logic = """
            if feedback_type == "applied_update":
                new_status = fields.get("applied", {}).get("stringValue", "no")
                url_field = fields.get("url", {}).get("stringValue", "")
                if url_field:
                    if 'applied_updates' not in locals():
                        applied_updates = {}
                    applied_updates[url_field] = new_status
                
                # Update status to "read"
                if doc_name:
                    update_url = f"https://firestore.googleapis.com/v1/{doc_name}?updateMask.fieldPaths=status"
                    payload = {"fields": {"status": {"stringValue": "read"}}}
                    requests.patch(update_url, json=payload, timeout=10)
                continue
"""

# Insert applied_update_logic before `reason = fields.get("reason"`
scraper_code = scraper_code.replace(
    '            reason = fields.get("reason", {}).get("stringValue", "")',
    applied_update_logic + '\n            reason = fields.get("reason", {}).get("stringValue", "")'
)

# Apply the applied_updates to jobs.json
applied_apply_logic = """
        if locals().get('applied_updates'):
            try:
                if os.path.exists(JOBS_FILE):
                    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                        jobs = json.load(f)
                    changed = False
                    for j in jobs:
                        if j.get('url') in applied_updates:
                            j['applied'] = applied_updates[j['url']]
                            changed = True
                    if changed:
                        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                            json.dump(jobs, f, indent=2)
                    print(f"INFO: Successfully synced applied status for {len(applied_updates)} jobs from the cloud.")
            except Exception as e:
                print(f"Error syncing applied status: {e}")
"""

# Insert before `if user_review_updates:`
scraper_code = scraper_code.replace(
    '        if user_review_updates:',
    applied_apply_logic + '\n        if user_review_updates:'
)

with open(SCRAPER_PATH, 'w', encoding='utf-8') as f:
    f.write(scraper_code)


# 2. Update index.html
with open(INDEX_PATH, 'r', encoding='utf-8') as f:
    index_code = f.read()

# Add global pagination vars
index_code = index_code.replace(
    'let sortAsc = true;',
    'let sortAsc = true;\n        let currentPage = 1;\n        const itemsPerPage = 100;\n        let filteredRows = [];'
)

# Fix toggleApplied call in buildTable
index_code = index_code.replace(
    '''<select class="status-pill ${appliedStatus === 'yes' ? 'yes' : (appliedStatus === 'Reject' ? 'no' : 'no')}" onchange="toggleApplied(this, '${job.url}')">''',
    '''<select class="status-pill ${appliedStatus === 'yes' ? 'yes' : (appliedStatus === 'Reject' ? 'no' : 'no')}" onchange="toggleApplied(this, '${job.url}', '${appliedStatus}')">'''
)

# Fix rereview counter
index_code = index_code.replace(
    '''if (tdSync.getAttribute("data-value") === 'Needs Re-review') counts.rereview++;''',
    '''if (tdSync.getAttribute("data-value") === 'Queued') counts.rereview++;'''
)

# Update filterTable to push to filteredRows instead of toggling display, then call renderPage
filter_loop = """
            filteredRows = [];
            rows.forEach(row => {
                let show = true;
"""
index_code = index_code.replace(
    """
            rows.forEach(row => {
                let show = true;
""",
    filter_loop
)

hide_row_logic = """
                if (show) {
                    filteredRows.push(row);
                    visibleCount++;
                    const tdMatches = row.getElementsByTagName("td")[9];
"""
index_code = index_code.replace(
    """
                row.style.display = show ? "" : "none";
                if (show) {
                    visibleCount++;
                    const tdMatches = row.getElementsByTagName("td")[9];
""",
    hide_row_logic
)

render_call = """
            const reviewedCounter = document.getElementById('reviewed-counter');
            if (reviewedCounter) reviewedCounter.textContent = reviewedCount;
            
            renderPage(1);
        }

        function renderPage(page) {
            currentPage = page;
            const start = (currentPage - 1) * itemsPerPage;
            const end = start + itemsPerPage;
            
            const tbody = document.querySelector('table tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            rows.forEach(row => {
                row.style.display = 'none';
            });
            
            for (let i = start; i < end && i < filteredRows.length; i++) {
                filteredRows[i].style.display = '';
            }
            
            updatePaginationUI();
        }

        function updatePaginationUI() {
            let container = document.getElementById('pagination-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'pagination-container';
                container.style = 'display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: var(--bg-card); border-top: 1px solid var(--border-color); border-radius: 0 0 1.25rem 1.25rem;';
                
                const tableContainer = document.querySelector('.table-container');
                if (tableContainer) {
                    tableContainer.appendChild(container);
                }
            }
            
            const totalPages = Math.ceil(filteredRows.length / itemsPerPage) || 1;
            
            container.innerHTML = `
                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                    Showing ${(currentPage - 1) * itemsPerPage + (filteredRows.length > 0 ? 1 : 0)} to ${Math.min(currentPage * itemsPerPage, filteredRows.length)} of ${filteredRows.length} entries
                </div>
                <div style="display: flex; gap: 0.5rem;">
                    <button onclick="changePage(-1)" style="padding: 0.4rem 0.8rem; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); color: white; border-radius: 0.5rem; cursor: ${currentPage > 1 ? 'pointer' : 'not-allowed'}; opacity: ${currentPage > 1 ? '1' : '0.5'};" ${currentPage <= 1 ? 'disabled' : ''}>Previous</button>
                    <div style="padding: 0.4rem 0.8rem; background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); color: white; border-radius: 0.5rem;">Page ${currentPage} of ${totalPages}</div>
                    <button onclick="changePage(1)" style="padding: 0.4rem 0.8rem; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); color: white; border-radius: 0.5rem; cursor: ${currentPage < totalPages ? 'pointer' : 'not-allowed'}; opacity: ${currentPage < totalPages ? '1' : '0.5'};" ${currentPage >= totalPages ? 'disabled' : ''}>Next</button>
                </div>
            `;
        }
        
        window.changePage = function(delta) {
            const totalPages = Math.ceil(filteredRows.length / itemsPerPage) || 1;
            let newPage = currentPage + delta;
            if (newPage < 1) newPage = 1;
            if (newPage > totalPages) newPage = totalPages;
            
            if (newPage !== currentPage) {
                renderPage(newPage);
                const scrollArea = document.querySelector('.table-scroll-area');
                if (scrollArea) scrollArea.scrollTop = 0;
            }
        };
"""
index_code = index_code.replace(
    """
            const reviewedCounter = document.getElementById('reviewed-counter');
            if (reviewedCounter) reviewedCounter.textContent = reviewedCount;
        }
""",
    render_call
)

# Sort table fix
sort_call = """
            rows.forEach(row => tbody.appendChild(row));
            
            filterTable();
        }
"""
index_code = index_code.replace(
    """
            rows.forEach(row => tbody.appendChild(row));
        }
""",
    sort_call
)


# Rewrite toggleApplied
new_toggle_applied = """
        async function toggleApplied(select, url, originalValue) {
            const newState = select.value;
            
            localStorage.setItem('applied_' + url, newState);
            
            if (typeof db !== 'undefined' && db !== null) {
                try {
                    select.disabled = true;
                    await db.collection("user_feedback").add({
                        url: url,
                        type: "applied_update",
                        applied: newState,
                        status: "unread",
                        timestamp: firebase.firestore.FieldValue.serverTimestamp()
                    });
                    
                    select.disabled = false;
                    select.className = 'status-pill ' + (newState === 'yes' ? 'yes' : (newState === 'Reject' ? 'no' : 'no'));
                    select.closest('td').setAttribute('data-value', newState);
                    select.setAttribute('onchange', `toggleApplied(this, '${url}', '${newState}')`);
                    
                    filterTable(); 
                    autoMarkUserReviewDone(url);
                } catch (e) {
                    console.error(e);
                    alert("Failed to sync applied status to cloud.");
                    select.value = originalValue;
                    select.disabled = false;
                }
            } else {
                select.className = 'status-pill ' + (newState === 'yes' ? 'yes' : (newState === 'Reject' ? 'no' : 'no'));
                select.closest('td').setAttribute('data-value', newState);
                filterTable(); 
                autoMarkUserReviewDone(url);
            }
        }
"""

old_toggle_applied = """
        async function toggleApplied(select, url) {
            const newState = select.value;
            
            localStorage.setItem('applied_' + url, newState);
            
            select.className = 'status-pill ' + (newState === 'yes' ? 'yes' : (newState === 'Reject' ? 'reject' : 'no'));
            
            const td = select.closest('td');
            td.setAttribute('data-value', newState);
            
            filterTable(); // Recalculate summary counts
            autoMarkUserReviewDone(url);
        }
"""

index_code = index_code.replace(old_toggle_applied, new_toggle_applied)

# remove border-radius on table-container to fit pagination
index_code = index_code.replace('border-radius: 1.25rem;', 'border-radius: 1.25rem 1.25rem 0 0;', 1)

with open(INDEX_PATH, 'w', encoding='utf-8') as f:
    f.write(index_code)

print("Patch applied to manju_jobs!")
