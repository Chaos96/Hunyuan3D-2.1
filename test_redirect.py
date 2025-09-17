#!/usr/bin/env python3
"""Test script to diagnose the 307 redirect issue"""

import requests
import urllib3
urllib3.disable_warnings()

def test_redirects():
    urls = [
        "https://157.10.162.253",
        "https://157.10.162.253/",
        "https://157.10.162.253//",
    ]

    for url in urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print('='*60)

        try:
            # Don't follow redirects
            response = requests.get(url, verify=False, allow_redirects=False)

            print(f"Status Code: {response.status_code}")
            print(f"Headers:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")

            if response.status_code in [301, 302, 303, 307, 308]:
                print(f"\n⚠️  REDIRECT TO: {response.headers.get('Location', 'No Location header')}")

        except Exception as e:
            print(f"Error: {e}")

def test_gradio_mount():
    """Test if the issue is related to how Gradio is mounted"""
    print("\n" + "="*60)
    print("ANALYSIS OF REDIRECT ISSUE")
    print("="*60)
    print("""
The issue appears to be in how FastAPI/Gradio handles path mounting:

1. When Gradio app is mounted at path="/", FastAPI may have issues with:
   - Root path normalization
   - Trailing slash handling

2. The double slash redirect suggests a bug in path concatenation:
   - Request: https://157.10.162.253 or https://157.10.162.253/
   - Redirect: https://157.10.162.253//  (double slash)

3. Possible causes:
   - gr.mount_gradio_app() path handling bug
   - Interaction between static file mount and root mount
   - URL path normalization in FastAPI/Starlette
""")

if __name__ == "__main__":
    test_redirects()
    test_gradio_mount()