import os

dashboard_path = r'c:\Users\vinee\manju_jobs\dashboard.html'
index_path = r'c:\Users\vinee\manju_jobs\firebase_app\index.html'

with open(dashboard_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject Firebase SDKs into head
firebase_sdk = """    <!-- Firebase Compat SDKs -->
    <script src="/__/firebase/10.7.1/firebase-app-compat.js"></script>
    <script src="/__/firebase/10.7.1/firebase-auth-compat.js"></script>
    <script src="/__/firebase/10.7.1/firebase-firestore-compat.js"></script>
</head>"""
content = content.replace('</head>', firebase_sdk)

# 2. Inject Auth UI into header
auth_ui = """        <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
            <div class="file-status-indicator">
                <div id="file-status-dot" class="status-dot"></div>
                <span id="file-status-text">Connecting...</span>
            </div>
            <!-- Auth Container -->
            <div id="auth-container" style="display: flex; gap: 1rem; align-items: center; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-color); border-radius: 2rem; padding: 0.25rem 0.25rem 0.25rem 1.25rem;">
                <span id="user-email" style="font-size: 0.875rem; color: var(--text-secondary); display: none;"></span>
                <button id="login-btn" style="background: #6366f1; color: white; border: none; padding: 0.5rem 1rem; border-radius: 2rem; cursor: pointer; font-family: 'Space Grotesk', sans-serif; font-weight: 600;">Sign in with Google</button>
                <button id="logout-btn" style="background: #ef4444; color: white; border: none; padding: 0.5rem 1rem; border-radius: 2rem; cursor: pointer; font-family: 'Space Grotesk', sans-serif; font-weight: 600; display: none;">Sign Out</button>
            </div>
        </div>
    </header>"""
content = content.replace("""        <div class="file-status-indicator">
            <div id="file-status-dot" class="status-dot"></div>
            <span id="file-status-text">Connecting...</span>
        </div>
    </header>""", auth_ui)

# 3. Inject Firebase init and logic at start of script
firebase_init = """    <script>
        // Initialize Firebase with explicit config
        const firebaseConfig = {
            projectId: "manju-jobs-dashboard",
            appId: "1:429610244337:web:6117ee37d384af03b33150",
            storageBucket: "manju-jobs-dashboard.firebasestorage.app",
            apiKey: "AIzaSyAWBGcQjYZ0oGlxkGMl5Rrm5eHxOZBRqa4",
            authDomain: "manju-jobs-dashboard.firebaseapp.com",
            messagingSenderId: "429610244337",
            measurementId: "G-EQ4XK63BVW"
        };
        firebase.initializeApp(firebaseConfig);

        const auth=firebase.auth();
        const db=firebase.firestore();

        // SECURITY GATE
        const ALLOWED_EMAILS=[ 'vineethkaimal1989@gmail.com', 'munchnambiar@gmail.com' ];
        
        let currentUser = null;
        let appliedJobsState = {};
        let firestoreUnsubscribe = null;
"""
content = content.replace('    <script>', firebase_init)

# 4. Inject setupUploadListeners / auth listener after DOMContentLoaded
dom_loaded = """        // Initial Data Fetch on load
        window.addEventListener('DOMContentLoaded', () => {
            // Setup Auth Listeners first!
            const loginBtn = document.getElementById('login-btn');
            const logoutBtn = document.getElementById('logout-btn');
            const userEmail = document.getElementById('user-email');
            const jobsContainer = document.getElementById('jobs-container');
            
            auth.onAuthStateChanged(user => {
                if (user) {
                    if (!ALLOWED_EMAILS.includes(user.email)) {
                        jobsContainer.innerHTML = '<div class="empty-state">Access Denied. Your email is not authorized to view this dashboard.</div>';
                        loginBtn.style.display = 'none';
                        logoutBtn.style.display = 'block';
                        userEmail.style.display = 'block';
                        userEmail.textContent = user.email + " (Unauthorized)";
                        return;
                    }

                    currentUser = user;
                    loginBtn.style.display = 'none';
                    logoutBtn.style.display = 'block';
                    userEmail.style.display = 'block';
                    userEmail.textContent = user.email;
                    
                    fetchJobsData();
                    setupUploadListeners();
                    
                    if (firestoreUnsubscribe) firestoreUnsubscribe();
                    firestoreUnsubscribe = db.collection('users').doc(user.uid).onSnapshot(doc => {
                        if (doc.exists) {
                            appliedJobsState = doc.data();
                        } else {
                            appliedJobsState = {};
                        }
                        if (allJobs.length > 0) buildTable();
                    });
                } else {
                    currentUser = null;
                    loginBtn.style.display = 'block';
                    logoutBtn.style.display = 'none';
                    userEmail.style.display = 'none';
                    userEmail.textContent = '';
                    appliedJobsState = {};
                    if (firestoreUnsubscribe) {
                        firestoreUnsubscribe();
                        firestoreUnsubscribe = null;
                    }
                    jobsContainer.innerHTML = '<div class="empty-state">Please Sign in with Google to view the dashboard.</div>';
                }
            });

            loginBtn.addEventListener('click', () => {
                const provider = new firebase.auth.GoogleAuthProvider();
                auth.signInWithPopup(provider).catch(console.error);
            });

            logoutBtn.addEventListener('click', () => {
                auth.signOut().catch(console.error);
            });
        });"""
content = content.replace("""        // Initial Data Fetch on load
        window.addEventListener('DOMContentLoaded', () => {
            fetchJobsData();
            setupUploadListeners();
        });""", dom_loaded)

# 5. Fix fetch URL
content = content.replace("fetch('jobs.json?nocache='", "fetch('https://vinchess1989.github.io/manju-jobs-dashboard/jobs.json?nocache='")

# 6. Fix table rows for firestore
table_row_old = """            // 3. Rows
            allJobs.forEach((job, index) => {
                const appliedStatus = localStorage.getItem('applied_' + job.url) || 'no';"""
table_row_new = """            // 3. Rows
            allJobs.forEach((job, index) => {
                const jobIdSafe = job.id || job.url.replace(/[\\.\\#\\$\\/\[\\]]/g, '_');
                let appliedStatus = 'no';
                if (currentUser && appliedJobsState[jobIdSafe]) {
                    appliedStatus = appliedJobsState[jobIdSafe];
                } else if (!currentUser) {
                    appliedStatus = localStorage.getItem('applied_' + job.url) || 'no';
                }"""
content = content.replace(table_row_old, table_row_new)

content = content.replace("""<button class="status-btn ${appliedStatus === 'yes' ? 'status-yes' : 'status-no'}" onclick="toggleApplied(this, '${job.url}')">${appliedStatus}</button>""", """<button class="status-btn ${appliedStatus === 'yes' ? 'status-yes' : 'status-no'}" onclick="toggleApplied(this, '${job.url}', '${jobIdSafe}')">${appliedStatus}</button>""")

# 7. Fix toggleApplied for firestore
toggle_applied_old = """        function toggleApplied(btn, jobUrl) {
            const currentStatus = btn.textContent.trim();
            const newStatus = currentStatus === 'no' ? 'yes' : 'no';

            btn.textContent = newStatus;
            btn.className = 'status-btn ' + (newStatus === 'yes' ? 'status-yes' : 'status-no');
            btn.parentElement.setAttribute('data-value', newStatus);

            localStorage.setItem('applied_' + jobUrl, newStatus);
        }"""
toggle_applied_new = """        function toggleApplied(btn, jobUrl, jobIdSafe) {
            const currentStatus = btn.textContent.trim();
            const newStatus = currentStatus === 'no' ? 'yes' : 'no';

            btn.textContent = newStatus;
            btn.className = 'status-btn ' + (newStatus === 'yes' ? 'status-yes' : 'status-no');
            btn.parentElement.setAttribute('data-value', newStatus);

            if (currentUser) {
                db.collection('users').doc(currentUser.uid).set({
                    [jobIdSafe]: newStatus
                }, { merge: true }).catch(err => {
                    console.error("Error saving to Firestore:", err);
                    alert("Failed to save to cloud. Reverting...");
                    btn.textContent = currentStatus;
                    btn.className = 'status-btn ' + (currentStatus === 'yes' ? 'status-yes' : 'status-no');
                    btn.parentElement.setAttribute('data-value', currentStatus);
                });
            } else {
                localStorage.setItem('applied_' + jobUrl, newStatus);
            }
        }"""
content = content.replace(toggle_applied_old, toggle_applied_new)

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("index.html fully regenerated from pristine dashboard.html")
