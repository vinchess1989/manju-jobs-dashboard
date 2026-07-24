import requests

FEEDBACK_URL = "https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents/user_feedback?pageSize=1000"
STATE_URL = "https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents/shared_state/job_status"

def backfill():
    print("Fetching user feedback...")
    resp = requests.get(FEEDBACK_URL, timeout=10)
    if resp.status_code != 200:
        print("Failed to fetch feedback:", resp.text)
        return

    data = resp.json()
    documents = data.get("documents", [])
    
    url_to_date = {}
    
    for doc in documents:
        fields = doc.get("fields", {})
        fb_type = fields.get("type", {}).get("stringValue", "")
        applied = fields.get("applied", {}).get("stringValue", "")
        if fb_type == "applied_update" and applied == "yes":
            url = fields.get("url", {}).get("stringValue", "")
            # Timestamps are typically auto-populated by the server in Firebase, or written directly.
            # But the client adds timestamp using serverTimestamp(). Let's see if updateTime is available.
            update_time = doc.get("updateTime", "")
            
            # The client sets it like this: timestamp: firebase.firestore.FieldValue.serverTimestamp()
            if url and update_time:
                date_str = update_time.split('T')[0]
                url_to_date[url] = date_str
                
    print(f"Found {len(url_to_date)} applied=yes updates.")
    
    if not url_to_date:
        return
        
    print("Fetching current shared state...")
    state_resp = requests.get(STATE_URL, timeout=10)
    state_doc = state_resp.json()
    state_fields = state_doc.get("fields", {})
    
    updates = 0
    for url, date_str in url_to_date.items():
        if url in state_fields:
            job_state = state_fields[url].get("mapValue", {}).get("fields", {})
            if job_state.get("applied", {}).get("stringValue") == "yes":
                if "applied_date" not in job_state:
                    job_state["applied_date"] = {"stringValue": date_str}
                    updates += 1

    if updates > 0:
        print(f"Applying {updates} updates...")
        patch_resp = requests.patch(STATE_URL, json={"fields": state_fields}, timeout=10)
        if patch_resp.status_code == 200:
            print("Successfully updated shared state.")
        else:
            print("Failed to update:", patch_resp.text)
    else:
        print("No missing applied_dates found in currently applied jobs.")

if __name__ == "__main__":
    backfill()
