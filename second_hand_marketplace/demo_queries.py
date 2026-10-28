"""
demo_queries.py - Meaningful SQL queries shown on the Admin > SQL Demo page.

Each query is a read-only SELECT. They are written so that students can
copy them straight into the MySQL command line during a viva.
"""

DEMO_QUERIES = [
    {
        "title": "Recent active products",
        "concepts": ["SELECT", "WHERE", "ORDER BY", "LIMIT"],
        "explain": "Shows the ten newest listings that are still for sale.",
        "sql": """SELECT product_id, title, price, item_condition, location, created_at
FROM products
WHERE status = 'active'
ORDER BY created_at DESC
LIMIT 10""",
    },
    {
        "title": "Keyword search with LIKE",
        "concepts": ["LIKE", "OR", "wildcards"],
        "explain": "The same pattern the search box uses: match the keyword in the title or description.",
        "sql": """SELECT product_id, title, price, location
FROM products
WHERE status = 'active'
  AND (title LIKE '%laptop%' OR description LIKE '%laptop%')
ORDER BY price""",
    },
    {
        "title": "Price range filter with BETWEEN",
        "concepts": ["BETWEEN", "AND", "ORDER BY"],
        "explain": "Products priced from Rs 5,000 to Rs 20,000.",
        "sql": """SELECT title, price, item_condition
FROM products
WHERE status = 'active' AND price BETWEEN 5000 AND 20000
ORDER BY price""",
    },
    {
        "title": "Location filter with IN",
        "concepts": ["IN", "ORDER BY"],
        "explain": "Listings from three chosen towns.",
        "sql": """SELECT title, price, location
FROM products
WHERE status = 'active' AND location IN ('Kochi', 'Kottayam', 'Ernakulam')
ORDER BY location, price""",
    },
    {
        "title": "Products per category (including empty ones)",
        "concepts": ["LEFT JOIN", "GROUP BY", "COUNT"],
        "explain": "LEFT JOIN keeps categories that currently have no active product.",
        "sql": """SELECT c.name AS category, COUNT(p.product_id) AS active_products
FROM categories c
LEFT JOIN products p
       ON p.category_id = c.category_id AND p.status = 'active'
GROUP BY c.category_id, c.name
ORDER BY active_products DESC, c.name""",
    },
    {
        "title": "Price statistics per category",
        "concepts": ["INNER JOIN", "GROUP BY", "AVG", "MIN", "MAX", "HAVING"],
        "explain": "Average, lowest and highest price for categories whose average is above Rs 3,000.",
        "sql": """SELECT c.name AS category,
       COUNT(*)            AS listings,
       ROUND(AVG(p.price)) AS avg_price,
       MIN(p.price)        AS min_price,
       MAX(p.price)        AS max_price
FROM products p
INNER JOIN categories c ON c.category_id = p.category_id
WHERE p.status = 'active'
GROUP BY c.category_id, c.name
HAVING AVG(p.price) > 3000
ORDER BY avg_price DESC""",
    },
    {
        "title": "Active sellers (two or more listings)",
        "concepts": ["INNER JOIN", "GROUP BY", "HAVING", "COUNT"],
        "explain": "HAVING filters groups after aggregation; WHERE could not do this.",
        "sql": """SELECT u.full_name AS seller, u.location, COUNT(p.product_id) AS total_listings
FROM users u
INNER JOIN products p ON p.seller_id = u.user_id
GROUP BY u.user_id, u.full_name, u.location
HAVING COUNT(p.product_id) >= 2
ORDER BY total_listings DESC, seller""",
    },
    {
        "title": "Products added in the last 30 days",
        "concepts": ["INNER JOIN", "DATE_SUB", "NOW()"],
        "explain": "Joins three tables to show the product, its category and its seller.",
        "sql": """SELECT p.title, c.name AS category, u.full_name AS seller, p.created_at
FROM products p
INNER JOIN categories c ON c.category_id = p.category_id
INNER JOIN users u      ON u.user_id = p.seller_id
WHERE p.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY p.created_at DESC""",
    },
    {
        "title": "Wishlists: who saved what",
        "concepts": ["INNER JOIN", "many-to-many", "ORDER BY"],
        "explain": "The wishlist table links users and products (a many-to-many relationship).",
        "sql": """SELECT u.full_name AS user_name, p.title AS product, p.price, w.created_at AS saved_on
FROM wishlist w
INNER JOIN users u    ON u.user_id = w.user_id
INNER JOIN products p ON p.product_id = w.product_id
ORDER BY w.created_at DESC""",
    },
    {
        "title": "Most wished-for products",
        "concepts": ["LEFT JOIN", "GROUP BY", "COUNT", "HAVING"],
        "explain": "Products saved by at least one user, most popular first.",
        "sql": """SELECT p.title, p.price, COUNT(w.wishlist_id) AS saved_by
FROM products p
LEFT JOIN wishlist w ON w.product_id = p.product_id
GROUP BY p.product_id, p.title, p.price
HAVING COUNT(w.wishlist_id) >= 1
ORDER BY saved_by DESC, p.title""",
    },
    {
        "title": "Inquiries received by each seller",
        "concepts": ["INNER JOIN", "GROUP BY", "COUNT", "SUM"],
        "explain": "Counts total and unread inquiries for every seller.",
        "sql": """SELECT s.full_name AS seller,
       COUNT(i.inquiry_id)                      AS inquiries,
       SUM(CASE WHEN i.is_read = 0 THEN 1 ELSE 0 END) AS unread
FROM inquiries i
INNER JOIN products p ON p.product_id = i.product_id
INNER JOIN users s    ON s.user_id = p.seller_id
GROUP BY s.user_id, s.full_name
ORDER BY inquiries DESC""",
    },
    {
        "title": "Listings that nobody has asked about",
        "concepts": ["LEFT JOIN", "IS NULL", "anti-join"],
        "explain": "LEFT JOIN + IS NULL finds rows with no match in the other table.",
        "sql": """SELECT p.title, p.price, p.location
FROM products p
LEFT JOIN inquiries i ON i.product_id = p.product_id
WHERE i.inquiry_id IS NULL AND p.status = 'active'
ORDER BY p.created_at DESC""",
    },
    {
        "title": "Registered users who never listed anything",
        "concepts": ["LEFT JOIN", "IS NULL"],
        "explain": "Buyers who have not become sellers yet.",
        "sql": """SELECT u.full_name, u.location, u.created_at
FROM users u
LEFT JOIN products p ON p.seller_id = u.user_id
WHERE p.product_id IS NULL AND u.role = 'user'""",
    },
    {
        "title": "Pending reports with product and reporter",
        "concepts": ["INNER JOIN", "WHERE", "ORDER BY"],
        "explain": "The work queue shown on the Admin Reports page.",
        "sql": """SELECT r.report_id, p.title AS product, rep.full_name AS reported_by, r.reason, r.created_at
FROM reports r
INNER JOIN products p  ON p.product_id = r.product_id
INNER JOIN users rep   ON rep.user_id = r.reporter_id
WHERE r.status = 'pending'
ORDER BY r.created_at""",
    },
    {
        "title": "Products priced above the overall average",
        "concepts": ["Subquery", "AVG", "WHERE"],
        "explain": "A scalar subquery calculates the average, then the outer query compares each price to it.",
        "sql": """SELECT title, price
FROM products
WHERE status = 'active'
  AND price > (SELECT AVG(price) FROM products WHERE status = 'active')
ORDER BY price DESC""",
    },
    {
        "title": "Condition breakdown",
        "concepts": ["GROUP BY", "COUNT", "AVG"],
        "explain": "How many items exist in each condition and what they cost on average.",
        "sql": """SELECT item_condition, COUNT(*) AS total, ROUND(AVG(price)) AS avg_price
FROM products
WHERE status = 'active'
GROUP BY item_condition
ORDER BY total DESC""",
    },
    {
        "title": "Busiest locations",
        "concepts": ["GROUP BY", "HAVING", "COUNT", "ORDER BY"],
        "explain": "Towns with at least two active listings.",
        "sql": """SELECT location, COUNT(*) AS listings
FROM products
WHERE status = 'active'
GROUP BY location
HAVING COUNT(*) >= 2
ORDER BY listings DESC, location""",
    },
    {
        "title": "Sales value per seller",
        "concepts": ["SUM", "GROUP BY", "INNER JOIN"],
        "explain": "Total value of items marked as sold by each seller.",
        "sql": """SELECT u.full_name AS seller, COUNT(*) AS items_sold, SUM(p.price) AS total_value
FROM products p
INNER JOIN users u ON u.user_id = p.seller_id
WHERE p.status = 'sold'
GROUP BY u.user_id, u.full_name""",
    },
]
