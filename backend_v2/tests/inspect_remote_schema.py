import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

# Load environment variables from backend_v2/.env or root .env
_pkg_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_pkg_env):
    load_dotenv(_pkg_env)
else:
    load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
service_role_key = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or os.environ.get("SUPABASE_KEY")
)

if not supabase_url or not service_role_key:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set in environment or .env")
    print("Example: export SUPABASE_URL='https://<project-ref>.supabase.co'")
    print("         export SUPABASE_SERVICE_ROLE_KEY='<service_role_key>'")
    sys.exit(1)

headers = {
    'apikey': service_role_key,
    'Authorization': f'Bearer {service_role_key}'
}
url = f"{supabase_url}/rest/v1/"
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())

print("=== DEFINITIONS ===")
for name in ['profiles', 'emergency_requests', 'appointments']:
    defn = data.get('definitions', {}).get(name, {})
    print(f"\n[{name}]")
    for prop, details in defn.get('properties', {}).items():
        print(f"  - {prop}: {details.get('type')}, format={details.get('format')}")

print("\n=== RPC PATHS ===")
for path, details in data.get('paths', {}).items():
    if path.startswith('/rpc/'):
        print(f"\n{path}:")
        for method, m_details in details.items():
            print(f"  method: {method.upper()}")
            print(f"  parameters: {m_details.get('parameters', [])}")
            print(f"  responses: {list(m_details.get('responses', {}).keys())}")

