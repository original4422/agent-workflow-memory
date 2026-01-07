"""Built-in demo HTML used by `python main.py --demo`.

This is a stub page to exercise the task-generation pipeline without relying on
network fetches or local HTML files.
"""

DEMO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Magento Admin - Dashboard</title>
</head>
<body>
    <div class="admin-header">
        <h1>Dashboard</h1>
        <nav>
            <a href="/admin/sales/order">Orders</a>
            <a href="/admin/catalog/product">Products</a>
            <a href="/admin/customer">Customers</a>
            <a href="/admin/reports">Reports</a>
        </nav>
    </div>
    
    <div class="dashboard-content">
        <div class="stats-widget">
            <h2>Lifetime Sales</h2>
            <p>$1,234,567.89</p>
        </div>
        
        <div class="stats-widget">
            <h2>Average Order</h2>
            <p>$125.50</p>
        </div>
        
        <div class="recent-orders">
            <h2>Recent Orders</h2>
            <table>
                <tr><th>Order ID</th><th>Customer</th><th>Total</th><th>Status</th></tr>
                <tr><td>100001</td><td>John Doe</td><td>$199.99</td><td>Complete</td></tr>
                <tr><td>100002</td><td>Jane Smith</td><td>$89.50</td><td>Processing</td></tr>
                <tr><td>100003</td><td>Bob Johnson</td><td>$450.00</td><td>Pending</td></tr>
            </table>
        </div>
        
        <div class="top-products">
            <h2>Best Selling Products (2023)</h2>
            <ol>
                <li>Impulse Duffle - 1,234 units</li>
                <li>Overnight Duffle - 987 units</li>
                <li>Quest Lumaflex Band - 876 units</li>
                <li>Sprite Yoga Companion Kit - 654 units</li>
                <li>Driven Backpack - 543 units</li>
            </ol>
        </div>
        
        <div class="customer-stats">
            <h2>Customer Statistics</h2>
            <ul>
                <li>Total Customers: 15,678</li>
                <li>New Customers (This Month): 234</li>
                <li>Top Customer: Emma Wilson ($12,345 total)</li>
            </ul>
        </div>
        
        <div class="search-section">
            <h3>Search Products</h3>
            <input type="text" placeholder="Enter product name or SKU" name="product_search">
            <button>Search</button>
        </div>
        
        <div class="quick-actions">
            <button>Add New Product</button>
            <button>Create Order</button>
            <button>View All Reports</button>
        </div>
    </div>
</body>
</html>
"""
