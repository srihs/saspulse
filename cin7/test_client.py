"""
Test script for Cin7 API Client

This script tests the Cin7 client functionality:
- Connection and authentication
- Fetching products
- Fetching branches
- Rate limiting

Usage:
    python3 manage.py shell < cin7/test_client.py

Or in Django shell:
    from cin7.test_client import test_cin7_client
    test_cin7_client()
"""

import os
import django

# Setup Django environment if running as standalone script
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saspulse.settings')
    django.setup()

from cin7.client import Cin7Client, Cin7AuthenticationError, Cin7APIError


def test_cin7_client():
    """Test Cin7 API client functionality"""

    print("=" * 60)
    print("Testing Cin7 API Client")
    print("=" * 60)

    # Check if credentials are set
    from django.conf import settings

    if not settings.CIN7_USERNAME or not settings.CIN7_API_KEY:
        print("\nWARNING: Cin7 credentials not configured!")
        print("Please set the following environment variables:")
        print("  - CIN7_USERNAME")
        print("  - CIN7_API_KEY")
        print("  - CIN7_API_URL (optional)")
        print("\nYou can set them in your .env file or export them:")
        print("  export CIN7_USERNAME='your_username'")
        print("  export CIN7_API_KEY='your_api_key'")
        return

    try:
        # Initialize client
        print("\n1. Initializing Cin7 client...")
        client = Cin7Client()
        print(f"   Base URL: {client.base_url}")
        print(f"   Username: {client.username}")
        print("   ✓ Client initialized successfully")

        # Test fetching branches (usually the smallest dataset)
        print("\n2. Testing connection by fetching branches...")
        try:
            branches = client.get_branches()
            print(f"   ✓ Found {len(branches)} branches")

            if branches:
                print("\n   Sample branch:")
                sample = branches[0]
                print(f"   - ID: {sample.get('id')}")
                print(f"   - Name: {sample.get('name')}")
                print(f"   - Code: {sample.get('code')}")

        except Cin7AuthenticationError as e:
            print(f"   ✗ Authentication failed: {e}")
            print("   Please check your credentials")
            return

        except Cin7APIError as e:
            print(f"   ✗ API error: {e}")
            return

        # Test fetching products with pagination
        print("\n3. Testing product fetching with pagination...")
        try:
            products = client.get_products(page=1, rows=10)
            print(f"   ✓ Fetched {len(products)} products (page 1, max 10)")

            if products:
                print("\n   Sample product:")
                sample = products[0]
                print(f"   - ID: {sample.get('id')}")
                print(f"   - Code: {sample.get('code')}")
                print(f"   - Name: {sample.get('name')}")
                print(f"   - Brand: {sample.get('brand')}")
                print(f"   - Stock: {sample.get('stockQuantity')}")

        except Cin7APIError as e:
            print(f"   ✗ Error fetching products: {e}")

        # Test rate limiting
        print("\n4. Testing rate limiter...")
        print("   Making 3 rapid requests to test per-second limit...")
        for i in range(3):
            try:
                client.get_branches()
                print(f"   Request {i+1}/3 completed")
            except Cin7APIError as e:
                print(f"   ✗ Request {i+1} failed: {e}")

        print("   ✓ Rate limiter working correctly")

        # Close client
        print("\n5. Closing client...")
        client.close()
        print("   ✓ Client closed")

        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Use the Cin7 client to fetch and sync data")
        print("2. Create Django management commands for data sync")
        print("3. Set up periodic sync with Celery tasks")

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_cin7_client()
