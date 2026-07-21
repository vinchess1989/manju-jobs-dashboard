import requests
import sys
import datetime

def main():
    if len(sys.argv) < 2:
        print("Usage: python update_status.py <status> [message]")
        sys.exit(1)
        
    status = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 else ""
    
    url = "https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents/shared_state/job_status?updateMask.fieldPaths=orchestrator_status"
    
    payload = {
        "fields": {
            "orchestrator_status": {
                "mapValue": {
                    "fields": {
                        "status": {"stringValue": status},
                        "message": {"stringValue": message},
                        "timestamp": {"timestampValue": datetime.datetime.utcnow().isoformat() + "Z"}
                    }
                }
            }
        }
    }
    
    resp = requests.patch(url, json=payload)
    if resp.status_code in (200, 201):
        print(f"Successfully updated status to {status}")
    else:
        print(f"Failed to update status: {resp.status_code} {resp.text}")

if __name__ == '__main__':
    main()
