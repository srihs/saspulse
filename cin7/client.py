"""
Cin7 API Client

Handles all communication with the Cin7 API including:
- Authentication (Basic Auth)
- Rate limiting (3/sec, 60/min, 5000/day)
- Error handling and retries
- Pagination
"""

import time
import base64
import logging
from collections import deque
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class Cin7APIError(Exception):
    """Base exception for Cin7 API errors"""
    pass


class Cin7RateLimitError(Cin7APIError):
    """Raised when rate limit is exceeded"""
    pass


class Cin7AuthenticationError(Cin7APIError):
    """Raised when authentication fails"""
    pass


class Cin7RateLimiter:
    """
    Manages Cin7 API rate limits:
    - 3 requests per second
    - 60 requests per minute
    - 5000 requests per day
    """

    def __init__(self):
        self.second_window = deque(maxlen=3)
        self.minute_window = deque(maxlen=60)
        self.daily_count_key = 'cin7_daily_api_count'

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Check per-second limit (3 requests)
        if len(self.second_window) >= 3:
            oldest = self.second_window[0]
            elapsed = now - oldest
            if elapsed < 1:
                sleep_time = 1 - elapsed
                logger.debug(f"Rate limit: sleeping {sleep_time:.2f}s for per-second limit")
                time.sleep(sleep_time)
                now = time.time()

        # Check per-minute limit (60 requests)
        if len(self.minute_window) >= 60:
            oldest = self.minute_window[0]
            elapsed = now - oldest
            if elapsed < 60:
                sleep_time = 60 - elapsed
                logger.debug(f"Rate limit: sleeping {sleep_time:.2f}s for per-minute limit")
                time.sleep(sleep_time)
                now = time.time()

        # Check daily limit (5000 requests)
        daily_count = cache.get(self.daily_count_key, 0)
        if daily_count >= 5000:
            raise Cin7RateLimitError("Daily API limit of 5000 requests exceeded")

        # Record this request
        self.second_window.append(now)
        self.minute_window.append(now)

        # Increment daily counter (expires at midnight)
        try:
            cache.add(self.daily_count_key, 0, timeout=86400)  # 24 hours
            cache.incr(self.daily_count_key)
        except:
            # If cache isn't available, just log and continue
            logger.warning("Cache not available for rate limiting")

    def reset_daily_counter(self):
        """Reset daily counter (should be called at midnight UTC)"""
        cache.set(self.daily_count_key, 0, timeout=86400)


class Cin7Client:
    """
    Cin7 API Client

    Usage:
        client = Cin7Client()
        products = client.get_products(where="brand='Nike'", page=1, rows=50)
    """

    def __init__(
        self,
        username: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library is required. Install with: pip install requests")

        self.username = username or settings.CIN7_USERNAME
        self.api_key = api_key or settings.CIN7_API_KEY
        self.base_url = (base_url or settings.CIN7_API_URL).rstrip('/')

        if not self.username or not self.api_key:
            raise Cin7AuthenticationError(
                "Cin7 credentials not provided. Set CIN7_USERNAME and CIN7_API_KEY "
                "in settings or pass them to Cin7Client()"
            )

        self.rate_limiter = Cin7RateLimiter()
        self.session = requests.Session()

        # Set up Basic Auth header
        credentials = f"{self.username}:{self.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {encoded}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Any:
        """
        Make HTTP request to Cin7 API with retries and rate limiting

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/Products')
            params: URL query parameters
            json_data: JSON request body
            max_retries: Maximum number of retry attempts

        Returns:
            Response JSON data

        Raises:
            Cin7APIError: If request fails after retries
            Cin7RateLimitError: If rate limit exceeded
            Cin7AuthenticationError: If authentication fails
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries):
            try:
                # Rate limiting
                self.rate_limiter.wait_if_needed()

                # Make request
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=30
                )

                # Handle response
                if response.status_code == 200:
                    logger.debug(f"Success: {method} {endpoint}")
                    return response.json() if response.content else None

                elif response.status_code == 401:
                    raise Cin7AuthenticationError(f"Invalid credentials: {response.text}")

                elif response.status_code == 429:
                    # Rate limit exceeded - exponential backoff
                    wait_time = (2 ** attempt) * 10  # 10s, 20s, 40s
                    logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                    time.sleep(wait_time)
                    continue

                elif response.status_code >= 500:
                    # Server error - retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                        logger.warning(f"Server error {response.status_code}, retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Cin7APIError(f"Server error {response.status_code}: {response.text}")

                else:
                    # Client error (400, 403, 404, etc.)
                    raise Cin7APIError(
                        f"API error {response.status_code}: {response.text}"
                    )

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"Request timeout, retrying {attempt+1}/{max_retries}")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise Cin7APIError("Request timeout after retries")

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Request failed: {e}, retrying {attempt+1}/{max_retries}")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise Cin7APIError(f"Request failed after retries: {e}")

        raise Cin7APIError(f"Failed after {max_retries} attempts")

    # ===== Products =====

    def get_products(
        self,
        where: Optional[str] = None,
        fields: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        rows: int = 250
    ) -> List[Dict]:
        """
        Get products from Cin7

        Args:
            where: Filter query (e.g., "brand='Nike' AND category='Shoes'")
            fields: Comma-separated fields to return
            order: Sort order (e.g., "createddate DESC")
            page: Page number (default: 1)
            rows: Results per page (default: 250, max: 250)

        Returns:
            List of product dictionaries
        """
        params = {'page': page, 'rows': min(rows, 250)}
        if where:
            params['where'] = where
        if fields:
            params['fields'] = fields
        if order:
            params['order'] = order

        return self._make_request('GET', '/Products', params=params)

    def get_product(self, product_id: int) -> Dict:
        """Get single product by ID"""
        return self._make_request('GET', f'/Products/{product_id}')

    def create_product(self, product_data: Dict) -> Dict:
        """Create new product"""
        return self._make_request('POST', '/Products', json_data=product_data)

    def update_product(self, product_data: Dict) -> Dict:
        """Update existing product"""
        return self._make_request('PUT', '/Products', json_data=product_data)

    # ===== Sales Orders =====

    def get_sales_orders(
        self,
        where: Optional[str] = None,
        fields: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        rows: int = 250
    ) -> List[Dict]:
        """Get sales orders from Cin7"""
        params = {'page': page, 'rows': min(rows, 250)}
        if where:
            params['where'] = where
        if fields:
            params['fields'] = fields
        if order:
            params['order'] = order

        return self._make_request('GET', '/SalesOrders', params=params)

    def get_sales_order(self, order_id: int) -> Dict:
        """Get single sales order by ID"""
        return self._make_request('GET', f'/SalesOrders/{order_id}')

    # ===== Purchase Orders =====

    def get_purchase_orders(
        self,
        where: Optional[str] = None,
        fields: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        rows: int = 250
    ) -> List[Dict]:
        """Get purchase orders from Cin7"""
        params = {'page': page, 'rows': min(rows, 250)}
        if where:
            params['where'] = where
        if fields:
            params['fields'] = fields
        if order:
            params['order'] = order

        return self._make_request('GET', '/PurchaseOrders', params=params)

    # ===== Contacts =====

    def get_contacts(
        self,
        where: Optional[str] = None,
        fields: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        rows: int = 250
    ) -> List[Dict]:
        """Get contacts (customers/suppliers) from Cin7"""
        params = {'page': page, 'rows': min(rows, 250)}
        if where:
            params['where'] = where
        if fields:
            params['fields'] = fields
        if order:
            params['order'] = order

        return self._make_request('GET', '/Contacts', params=params)

    # ===== Stock =====

    def get_stock(
        self,
        where: Optional[str] = None,
        barcode: Optional[str] = None,
        fields: Optional[str] = None,
        page: int = 1,
        rows: int = 250
    ) -> List[Dict]:
        """
        Get stock/inventory from Cin7

        Args:
            where: Filter query
            barcode: Lookup by barcode
            fields: Comma-separated fields to return
            page: Page number
            rows: Results per page
        """
        params = {'page': page, 'rows': min(rows, 250)}
        if where:
            params['where'] = where
        if barcode:
            params['barcode'] = barcode
        if fields:
            params['fields'] = fields

        return self._make_request('GET', '/Stock', params=params)

    # ===== Branches =====

    def get_branches(self) -> List[Dict]:
        """Get all branches/warehouses"""
        return self._make_request('GET', '/Branches')

    def close(self):
        """Close the HTTP session"""
        self.session.close()
