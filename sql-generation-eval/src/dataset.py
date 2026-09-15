"""Author the draft question catalog; export once, then review data/items.jsonl."""

from __future__ import annotations

import json
import textwrap

from .common import DATA

# Common gold-query building blocks. These are never sent to a model.
LINE_SALES = """
approved_refunds AS (
 SELECT ri.order_item_id, SUM(ri.refund_cents) AS refund_cents,
        SUM(ri.quantity) AS returned_quantity
 FROM return_items ri JOIN returns r ON r.return_id=ri.return_id
 WHERE r.status='approved' GROUP BY ri.order_item_id
), sales AS (
 SELECT o.order_id, o.customer_id, o.ordered_at, oi.order_item_id, oi.product_id,
        oi.quantity, oi.quantity*oi.unit_price_cents-oi.discount_cents AS gross_cents,
        COALESCE(ar.refund_cents,0) AS refund_cents,
        oi.quantity*oi.unit_price_cents-oi.discount_cents-COALESCE(ar.refund_cents,0) AS net_cents,
        oi.quantity-COALESCE(ar.returned_quantity,0) AS retained_quantity
 FROM orders o JOIN order_items oi ON oi.order_id=o.order_id
 LEFT JOIN approved_refunds ar ON ar.order_item_id=oi.order_item_id
 WHERE o.status='completed'
)"""
ROOT_CATEGORIES = """
tree(category_id, root_id) AS (
 SELECT category_id, category_id FROM categories WHERE parent_category_id IS NULL
 UNION ALL
 SELECT c.category_id, t.root_id FROM categories c JOIN tree t ON c.parent_category_id=t.category_id
)"""


def catalog() -> list[dict]:
    items: list[dict] = []

    def add(split: str, difficulty: str, skill: str, question: str, columns: list[str], sql: str, ordered: bool = True) -> None:
        number = 1 + sum(item["split"] == split for item in items)
        items.append({"id": f"{split}_{number:02}", "split": split, "difficulty": difficulty,
                      "skill": skill, "question": question, "expected_columns": columns,
                      "ordered": ordered, "reference_sql": textwrap.dedent(sql).strip(),
                      "review_status": "draft_unreviewed", "reviewers": []})

    add("dev", "easy", "filter", "Return customer_id and email for customers whose country is TN, ordered by customer_id.", ["customer_id", "email"],
        "SELECT customer_id,email FROM customers WHERE country='TN' ORDER BY customer_id")
    add("dev", "easy", "filter", "Return product_id and current_price_cents for active products priced above 10000 cents, ordered by product_id.", ["product_id", "current_price_cents"],
        "SELECT product_id,current_price_cents FROM products WHERE active=1 AND current_price_cents>10000 ORDER BY product_id")
    add("dev", "easy", "self_join", "Return category_id and category_name for immediate children of Electronics, ordered by category_id.", ["category_id", "category_name"],
        "SELECT c.category_id,c.category_name FROM categories c JOIN categories p ON p.category_id=c.parent_category_id WHERE p.category_name='Electronics' ORDER BY c.category_id")
    add("dev", "medium", "having", "Return customer_id and completed_order_count for customers with at least 5 completed orders, ordered by customer_id.", ["customer_id", "completed_order_count"],
        "SELECT customer_id,COUNT(*) FROM orders WHERE status='completed' GROUP BY customer_id HAVING COUNT(*)>=5 ORDER BY customer_id")
    add("dev", "medium", "conditional_aggregation", "For each payment method, return method and failed_amount_cents, including methods with zero failed payments. Order by method.", ["method", "failed_amount_cents"],
        "SELECT method,SUM(CASE WHEN status='failed' THEN amount_cents ELSE 0 END) FROM payments GROUP BY method ORDER BY method")
    add("dev", "medium", "anti_join", "Return customer_id for customers who have never placed any order of any status, ordered by customer_id.", ["customer_id"],
        "SELECT c.customer_id FROM customers c WHERE NOT EXISTS(SELECT 1 FROM orders o WHERE o.customer_id=c.customer_id) ORDER BY c.customer_id")
    add("dev", "medium", "multi_join", "Return product_id, supplier_count and minimum_lead_days for each product with a supplier. Order by product_id.", ["product_id", "supplier_count", "minimum_lead_days"],
        "SELECT product_id,COUNT(*),MIN(lead_time_days) FROM product_suppliers GROUP BY product_id ORDER BY product_id")
    add("dev", "hard", "net_revenue", "Return customer_id and net_revenue_cents for customers with completed orders in January 2025. Order by customer_id.", ["customer_id", "net_revenue_cents"],
        "WITH " + LINE_SALES + " SELECT customer_id,SUM(net_cents) FROM sales WHERE ordered_at>='2025-01-01' AND ordered_at<'2025-02-01' GROUP BY customer_id ORDER BY customer_id")
    add("dev", "hard", "window", "Return the five most expensive products as product_id, current_price_cents and price_rank, using dense rank by price descending. Sort by price descending, then product_id ascending; return exactly five rows.", ["product_id", "current_price_cents", "price_rank"],
        "SELECT product_id,current_price_cents,DENSE_RANK() OVER(ORDER BY current_price_cents DESC) FROM products ORDER BY current_price_cents DESC,product_id LIMIT 5")
    add("dev", "hard", "recursive_cte", "Return category_id and depth for all categories below Electronics, excluding Electronics itself. Depth 1 means an immediate child. Order by depth then category_id.", ["category_id", "depth"],
        "WITH RECURSIVE t(category_id,depth) AS (SELECT category_id,0 FROM categories WHERE category_name='Electronics' UNION ALL SELECT c.category_id,t.depth+1 FROM categories c JOIN t ON c.parent_category_id=t.category_id) SELECT category_id,depth FROM t WHERE depth>0 ORDER BY depth,category_id")

    add("test", "easy", "filter", "Return product_id, product_name and current_price_cents for active products priced between 2500 and 12000 cents inclusive. Sort by price descending then product_id ascending.", ["product_id", "product_name", "current_price_cents"],
        "SELECT product_id,product_name,current_price_cents FROM products WHERE active=1 AND current_price_cents BETWEEN 2500 AND 12000 ORDER BY current_price_cents DESC,product_id")
    add("test", "easy", "left_join", "Return every customer_id and address_count, including customers with no addresses. Order by customer_id.", ["customer_id", "address_count"],
        "SELECT c.customer_id,COUNT(a.address_id) FROM customers c LEFT JOIN addresses a ON a.customer_id=c.customer_id GROUP BY c.customer_id ORDER BY c.customer_id")
    add("test", "easy", "left_join", "Return every category_id and directly_assigned_product_count, including empty categories. Order by category_id.", ["category_id", "directly_assigned_product_count"],
        "SELECT c.category_id,COUNT(p.product_id) FROM categories c LEFT JOIN products p ON p.category_id=c.category_id GROUP BY c.category_id ORDER BY c.category_id")
    add("test", "easy", "aggregation", "Return order_id and pending_amount_cents for orders with pending payments, ordered by order_id.", ["order_id", "pending_amount_cents"],
        "SELECT order_id,SUM(amount_cents) FROM payments WHERE status='pending' GROUP BY order_id ORDER BY order_id")
    add("test", "easy", "null", "Return shipment_id, order_id and promised_at for undelivered shipments, sorted by promised_at then shipment_id.", ["shipment_id", "order_id", "promised_at"],
        "SELECT shipment_id,order_id,promised_at FROM shipments WHERE delivered_at IS NULL ORDER BY promised_at,shipment_id")
    add("test", "easy", "date_boundary", "Return order_id and customer_id for completed orders placed during Q2 2025. Order by order_id.", ["order_id", "customer_id"],
        "SELECT order_id,customer_id FROM orders WHERE status='completed' AND ordered_at>='2025-04-01' AND ordered_at<'2025-07-01' ORDER BY order_id")
    add("test", "easy", "aggregation", "Return status and order_count for all order statuses present in the database. Order by status.", ["status", "order_count"],
        "SELECT status,COUNT(*) FROM orders GROUP BY status ORDER BY status")
    add("test", "easy", "duplicates", "Return one country value for each customer. Preserve duplicate country values; row order does not matter.", ["country"],
        "SELECT country FROM customers", ordered=False)
    add("test", "medium", "left_join", "Return every customer_id and completed_order_count, including zero counts. Order by customer_id.", ["customer_id", "completed_order_count"],
        "SELECT c.customer_id,COUNT(o.order_id) FROM customers c LEFT JOIN orders o ON o.customer_id=c.customer_id AND o.status='completed' GROUP BY c.customer_id ORDER BY c.customer_id")
    add("test", "medium", "multi_join", "Return customer_id and gross_revenue_cents for customers with completed orders, ordered by customer_id.", ["customer_id", "gross_revenue_cents"],
        "SELECT o.customer_id,SUM(oi.quantity*oi.unit_price_cents-oi.discount_cents) FROM orders o JOIN order_items oi ON oi.order_id=o.order_id WHERE o.status='completed' GROUP BY o.customer_id ORDER BY o.customer_id")
    add("test", "medium", "multi_join", "Return category_id and gross_revenue_cents for directly assigned categories with completed sales. Order by category_id.", ["category_id", "gross_revenue_cents"],
        "SELECT p.category_id,SUM(oi.quantity*oi.unit_price_cents-oi.discount_cents) FROM orders o JOIN order_items oi ON oi.order_id=o.order_id JOIN products p ON p.product_id=oi.product_id WHERE o.status='completed' GROUP BY p.category_id ORDER BY p.category_id")
    add("test", "medium", "distinct", "Return distinct product_id values bought in completed orders by customers whose country is FR. Order by product_id.", ["product_id"],
        "SELECT DISTINCT oi.product_id FROM customers c JOIN orders o ON o.customer_id=c.customer_id JOIN order_items oi ON oi.order_id=o.order_id WHERE c.country='FR' AND o.status='completed' ORDER BY oi.product_id")
    add("test", "medium", "anti_join", "Return product_id for products never sold in any completed order, ordered by product_id.", ["product_id"],
        "SELECT p.product_id FROM products p WHERE NOT EXISTS(SELECT 1 FROM order_items oi JOIN orders o ON o.order_id=oi.order_id WHERE oi.product_id=p.product_id AND o.status='completed') ORDER BY p.product_id")
    add("test", "medium", "anti_join", "Return customer_id for customers with at least one completed order and no approved return on any of their orders. Order by customer_id.", ["customer_id"],
        "SELECT c.customer_id FROM customers c WHERE EXISTS(SELECT 1 FROM orders o WHERE o.customer_id=c.customer_id AND o.status='completed') AND NOT EXISTS(SELECT 1 FROM orders o JOIN returns r ON r.order_id=o.order_id WHERE o.customer_id=c.customer_id AND r.status='approved') ORDER BY c.customer_id")
    add("test", "medium", "conditional_aggregation", "Return every order_id and collected_cents, including zero successful collections. Order by order_id.", ["order_id", "collected_cents"],
        "SELECT o.order_id,COALESCE(SUM(CASE WHEN p.status='succeeded' THEN p.amount_cents ELSE 0 END),0) FROM orders o LEFT JOIN payments p ON p.order_id=o.order_id GROUP BY o.order_id ORDER BY o.order_id")
    add("test", "medium", "having", "Return order_id and successful_payment_count for orders with more than one successful payment. Order by order_id.", ["order_id", "successful_payment_count"],
        "SELECT order_id,COUNT(*) FROM payments WHERE status='succeeded' GROUP BY order_id HAVING COUNT(*)>1 ORDER BY order_id")
    add("test", "medium", "having", "Return order_id and distinct_product_count for completed orders containing at least three different products. Order by order_id.", ["order_id", "distinct_product_count"],
        "SELECT o.order_id,COUNT(DISTINCT oi.product_id) FROM orders o JOIN order_items oi ON oi.order_id=o.order_id WHERE o.status='completed' GROUP BY o.order_id HAVING COUNT(DISTINCT oi.product_id)>=3 ORDER BY o.order_id")
    add("test", "medium", "many_to_many", "Return every supplier_id and active_product_count, including suppliers with zero active products. Order by supplier_id.", ["supplier_id", "active_product_count"],
        "SELECT s.supplier_id,COUNT(p.product_id) FROM suppliers s LEFT JOIN product_suppliers ps ON ps.supplier_id=s.supplier_id LEFT JOIN products p ON p.product_id=ps.product_id AND p.active=1 GROUP BY s.supplier_id ORDER BY s.supplier_id")
    add("test", "medium", "anti_join", "Return product_id for products with no supplier relationship, ordered by product_id.", ["product_id"],
        "SELECT p.product_id FROM products p LEFT JOIN product_suppliers ps ON ps.product_id=p.product_id WHERE ps.supplier_id IS NULL ORDER BY p.product_id")
    add("test", "medium", "multi_join", "Return customer_id and approved_refund_cents for customers with approved returns, ordered by customer_id.", ["customer_id", "approved_refund_cents"],
        "SELECT o.customer_id,SUM(ri.refund_cents) FROM orders o JOIN returns r ON r.order_id=o.order_id JOIN return_items ri ON ri.return_id=r.return_id WHERE r.status='approved' GROUP BY o.customer_id ORDER BY o.customer_id")
    add("test", "medium", "distinct", "Return customer_id and late_order_count for customers with completed orders containing at least one late delivered shipment. Count each order once. Order by customer_id.", ["customer_id", "late_order_count"],
        "SELECT o.customer_id,COUNT(DISTINCT o.order_id) FROM orders o JOIN shipments s ON s.order_id=o.order_id WHERE o.status='completed' AND s.delivered_at>s.promised_at GROUP BY o.customer_id ORDER BY o.customer_id")
    add("test", "medium", "null", "Return order_id for processing orders with no shipments, ordered by order_id.", ["order_id"],
        "SELECT o.order_id FROM orders o LEFT JOIN shipments s ON s.order_id=o.order_id WHERE o.status='processing' AND s.shipment_id IS NULL ORDER BY o.order_id")
    add("test", "medium", "correlated_subquery", "Return product_id and category_id for products priced strictly above the average current price of all products directly assigned to the same category. Order by product_id.", ["product_id", "category_id"],
        "SELECT p.product_id,p.category_id FROM products p WHERE p.current_price_cents>(SELECT AVG(p2.current_price_cents) FROM products p2 WHERE p2.category_id=p.category_id) ORDER BY p.product_id")
    add("test", "medium", "anti_join", "Return customer_id for customers with completed orders in July 2025 but none in August 2025. Order by customer_id.", ["customer_id"],
        "SELECT DISTINCT a.customer_id FROM orders a WHERE a.status='completed' AND a.ordered_at>='2025-07-01' AND a.ordered_at<'2025-08-01' AND NOT EXISTS(SELECT 1 FROM orders b WHERE b.customer_id=a.customer_id AND b.status='completed' AND b.ordered_at>='2025-08-01' AND b.ordered_at<'2025-09-01') ORDER BY a.customer_id")

    add("test", "hard", "net_revenue", "Return customer_id and net_revenue_cents for customers with completed orders in Q2 2025. Order by customer_id.", ["customer_id", "net_revenue_cents"],
        "WITH " + LINE_SALES + " SELECT customer_id,SUM(net_cents) FROM sales WHERE ordered_at>='2025-04-01' AND ordered_at<'2025-07-01' GROUP BY customer_id ORDER BY customer_id")
    add("test", "hard", "window", "For each directly assigned category, return up to three products with the highest net revenue from completed orders in Q2 2025. Return category_id, product_id and net_revenue_cents. Exclude unsold products. Break revenue ties by smaller product_id. Order by category_id, revenue descending, product_id.", ["category_id", "product_id", "net_revenue_cents"],
        "WITH " + LINE_SALES + ", totals AS (SELECT p.category_id,s.product_id,SUM(s.net_cents) AS revenue FROM sales s JOIN products p ON p.product_id=s.product_id WHERE s.ordered_at>='2025-04-01' AND s.ordered_at<'2025-07-01' GROUP BY p.category_id,s.product_id), ranked AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY category_id ORDER BY revenue DESC,product_id) AS rn FROM totals) SELECT category_id,product_id,revenue FROM ranked WHERE rn<=3 ORDER BY category_id,revenue DESC,product_id")
    add("test", "hard", "fanout", "For every completed order, return order_id, gross_merchandise_cents, collected_cents and shipment_count. Include zero collections and zero shipments. Count each source exactly once. Order by order_id.", ["order_id", "gross_merchandise_cents", "collected_cents", "shipment_count"],
        "WITH i AS (SELECT order_id,SUM(quantity*unit_price_cents-discount_cents) AS gross FROM order_items GROUP BY order_id), p AS (SELECT order_id,SUM(amount_cents) AS paid FROM payments WHERE status='succeeded' GROUP BY order_id), s AS (SELECT order_id,COUNT(*) AS n FROM shipments GROUP BY order_id) SELECT o.order_id,COALESCE(i.gross,0),COALESCE(p.paid,0),COALESCE(s.n,0) FROM orders o LEFT JOIN i ON i.order_id=o.order_id LEFT JOIN p ON p.order_id=o.order_id LEFT JOIN s ON s.order_id=o.order_id WHERE o.status='completed' ORDER BY o.order_id")
    add("test", "hard", "window", "For each calendar month with completed sales in 2025, return month (YYYY-MM), net_revenue_cents and cumulative_net_revenue_cents since January. Order by month.", ["month", "net_revenue_cents", "cumulative_net_revenue_cents"],
        "WITH " + LINE_SALES + ", m AS (SELECT substr(ordered_at,1,7) AS month,SUM(net_cents) AS revenue FROM sales WHERE ordered_at>='2025-01-01' AND ordered_at<'2026-01-01' GROUP BY month) SELECT month,revenue,SUM(revenue) OVER(ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM m ORDER BY month")
    add("test", "hard", "window", "For each calendar month with completed sales in 2025, return month (YYYY-MM), net_revenue_cents and change_from_previous_month_cents. The first month's change is NULL. Order by month.", ["month", "net_revenue_cents", "change_from_previous_month_cents"],
        "WITH " + LINE_SALES + ", m AS (SELECT substr(ordered_at,1,7) AS month,SUM(net_cents) AS revenue FROM sales WHERE ordered_at>='2025-01-01' AND ordered_at<'2026-01-01' GROUP BY month) SELECT month,revenue,revenue-LAG(revenue) OVER(ORDER BY month) FROM m ORDER BY month")
    add("test", "hard", "consecutive_periods", "Return customer_id for customers whose gross merchandise spending strictly increased from January to February and from February to March 2025. Require completed orders in all three months. Order by customer_id.", ["customer_id"],
        "WITH " + LINE_SALES + ", m AS (SELECT customer_id,substr(ordered_at,1,7) AS month,SUM(gross_cents) AS gross FROM sales GROUP BY customer_id,month) SELECT a.customer_id FROM m a JOIN m b ON b.customer_id=a.customer_id AND b.month='2025-02' JOIN m c ON c.customer_id=a.customer_id AND c.month='2025-03' WHERE a.month='2025-01' AND a.gross<b.gross AND b.gross<c.gross ORDER BY a.customer_id")
    add("test", "hard", "recursive_cte", "Return every root_category_id, root_category_name and net_revenue_cents across all products assigned anywhere in its category subtree. Include roots with zero completed sales. Order by root_category_id.", ["root_category_id", "root_category_name", "net_revenue_cents"],
        "WITH RECURSIVE " + ROOT_CATEGORIES + ", " + LINE_SALES + " SELECT root.category_id,root.category_name,COALESCE(SUM(s.net_cents),0) FROM categories root LEFT JOIN tree t ON t.root_id=root.category_id LEFT JOIN products p ON p.category_id=t.category_id LEFT JOIN sales s ON s.product_id=p.product_id WHERE root.parent_category_id IS NULL GROUP BY root.category_id,root.category_name ORDER BY root.category_id")
    add("test", "hard", "relational_division", "Return supplier_id for suppliers that supply every active product directly assigned to category_id 11. Order by supplier_id.", ["supplier_id"],
        "SELECT s.supplier_id FROM suppliers s WHERE NOT EXISTS(SELECT 1 FROM products p WHERE p.active=1 AND p.category_id=11 AND NOT EXISTS(SELECT 1 FROM product_suppliers ps WHERE ps.supplier_id=s.supplier_id AND ps.product_id=p.product_id)) ORDER BY s.supplier_id")
    add("test", "hard", "net_quantity", "Return product_id, sold_quantity, approved_returned_quantity and retained_quantity for products sold in completed orders. Order by product_id.", ["product_id", "sold_quantity", "approved_returned_quantity", "retained_quantity"],
        "WITH " + LINE_SALES + " SELECT product_id,SUM(quantity),SUM(quantity-retained_quantity),SUM(retained_quantity) FROM sales GROUP BY product_id ORDER BY product_id")
    add("test", "hard", "ratio", "Return directly assigned category_id and approved_unit_return_rate, defined as approved returned units divided by units sold in completed orders. Include categories with sales even if their return rate is zero. Order by category_id.", ["category_id", "approved_unit_return_rate"],
        "WITH " + LINE_SALES + " SELECT p.category_id,1.0*SUM(s.quantity-s.retained_quantity)/SUM(s.quantity) FROM sales s JOIN products p ON p.product_id=s.product_id GROUP BY p.category_id ORDER BY p.category_id")
    add("test", "hard", "window", "For each customer with a completed order, return customer_id, first_order_id and first_order_date. Break equal dates by the smaller order_id. Order by customer_id.", ["customer_id", "first_order_id", "first_order_date"],
        "WITH ranked AS (SELECT customer_id,order_id,ordered_at,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY ordered_at,order_id) AS rn FROM orders WHERE status='completed') SELECT customer_id,order_id,ordered_at FROM ranked WHERE rn=1 ORDER BY customer_id")
    add("test", "hard", "window", "For each customer with at least two completed orders, return customer_id, second_order_id and second_order_date. Sort orders by ordered_at then order_id to identify the second order. Order results by customer_id.", ["customer_id", "second_order_id", "second_order_date"],
        "WITH ranked AS (SELECT customer_id,order_id,ordered_at,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY ordered_at,order_id) AS rn FROM orders WHERE status='completed') SELECT customer_id,order_id,ordered_at FROM ranked WHERE rn=2 ORDER BY customer_id")
    add("test", "hard", "window", "Return customer_id and longest_gap_days between consecutive completed orders for customers with at least two completed orders. Order each customer's orders by ordered_at then order_id. Order results by customer_id.", ["customer_id", "longest_gap_days"],
        "WITH gaps AS (SELECT customer_id,julianday(ordered_at)-julianday(LAG(ordered_at) OVER(PARTITION BY customer_id ORDER BY ordered_at,order_id)) AS gap FROM orders WHERE status='completed') SELECT customer_id,MAX(gap) FROM gaps GROUP BY customer_id HAVING COUNT(gap)>0 ORDER BY customer_id")
    add("test", "hard", "window", "Return country, customer_id and net_revenue_cents for up to two customers with highest net revenue in each customer country. Include only customers with completed orders. Break ties by customer_id. Order by country, revenue descending, customer_id.", ["country", "customer_id", "net_revenue_cents"],
        "WITH " + LINE_SALES + ", totals AS (SELECT c.country,s.customer_id,SUM(s.net_cents) AS revenue FROM sales s JOIN customers c ON c.customer_id=s.customer_id GROUP BY c.country,s.customer_id), ranked AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY country ORDER BY revenue DESC,customer_id) AS rn FROM totals) SELECT country,customer_id,revenue FROM ranked WHERE rn<=2 ORDER BY country,revenue DESC,customer_id")
    add("test", "hard", "window", "Return category_id, product_id, net_revenue_cents and category_revenue_share for products with completed sales, using directly assigned categories. The share is product net revenue divided by its category's total net revenue, or NULL if that total is zero. Order by category_id then product_id.", ["category_id", "product_id", "net_revenue_cents", "category_revenue_share"],
        "WITH " + LINE_SALES + ", totals AS (SELECT p.category_id,s.product_id,SUM(s.net_cents) AS revenue FROM sales s JOIN products p ON p.product_id=s.product_id GROUP BY p.category_id,s.product_id) SELECT category_id,product_id,revenue,1.0*revenue/NULLIF(SUM(revenue) OVER(PARTITION BY category_id),0) FROM totals ORDER BY category_id,product_id")
    add("test", "hard", "multi_join", "Return supplier_id and gross_revenue_cents of completed sales of the products each supplier can supply. Attribute the full product revenue to each eligible supplier, counting each sold line once per supplier. Include suppliers with zero sales. Order by supplier_id.", ["supplier_id", "gross_revenue_cents"],
        "WITH " + LINE_SALES + ", p AS (SELECT product_id,SUM(gross_cents) AS gross FROM sales GROUP BY product_id) SELECT s.supplier_id,COALESCE(SUM(p.gross),0) FROM suppliers s LEFT JOIN product_suppliers ps ON ps.supplier_id=s.supplier_id LEFT JOIN p ON p.product_id=ps.product_id GROUP BY s.supplier_id ORDER BY s.supplier_id")
    add("test", "hard", "anti_join", "Return customer_id and completed_order_count for customers with at least three completed orders and no late delivered shipment on any completed order. Order by customer_id.", ["customer_id", "completed_order_count"],
        "SELECT o.customer_id,COUNT(*) FROM orders o WHERE o.status='completed' AND NOT EXISTS(SELECT 1 FROM orders x JOIN shipments s ON s.order_id=x.order_id WHERE x.customer_id=o.customer_id AND x.status='completed' AND s.delivered_at>s.promised_at) GROUP BY o.customer_id HAVING COUNT(*)>=3 ORDER BY o.customer_id")
    add("test", "hard", "fanout", "For each completed order having any approved return, return order_id, gross_merchandise_cents, approved_refund_cents and collected_cents. Each amount must be counted once despite multiple line items and payments. Order by order_id.", ["order_id", "gross_merchandise_cents", "approved_refund_cents", "collected_cents"],
        "WITH " + LINE_SALES + ", totals AS (SELECT order_id,SUM(gross_cents) AS gross,SUM(refund_cents) AS refunds FROM sales GROUP BY order_id), paid AS (SELECT order_id,SUM(amount_cents) AS collected FROM payments WHERE status='succeeded' GROUP BY order_id) SELECT t.order_id,t.gross,t.refunds,COALESCE(p.collected,0) FROM totals t LEFT JOIN paid p ON p.order_id=t.order_id WHERE EXISTS(SELECT 1 FROM returns r WHERE r.order_id=t.order_id AND r.status='approved') ORDER BY t.order_id")
    add("test", "hard", "self_join", "Return product_a_id, product_b_id and completed_order_count for unordered pairs of different products bought together in at least two completed orders. Require product_a_id < product_b_id and count each order once per pair. Order by order count descending, then product_a_id, product_b_id.", ["product_a_id", "product_b_id", "completed_order_count"],
        "SELECT a.product_id,b.product_id,COUNT(DISTINCT a.order_id) FROM order_items a JOIN order_items b ON b.order_id=a.order_id AND a.product_id<b.product_id JOIN orders o ON o.order_id=a.order_id WHERE o.status='completed' GROUP BY a.product_id,b.product_id HAVING COUNT(DISTINCT a.order_id)>=2 ORDER BY COUNT(DISTINCT a.order_id) DESC,a.product_id,b.product_id")
    add("test", "hard", "relational_division", "Return customer_id for customers who bought products from every root category in completed orders, counting descendant categories as belonging to their root. Order by customer_id.", ["customer_id"],
        "WITH RECURSIVE " + ROOT_CATEGORIES + " SELECT o.customer_id FROM orders o JOIN order_items oi ON oi.order_id=o.order_id JOIN products p ON p.product_id=oi.product_id JOIN tree t ON t.category_id=p.category_id WHERE o.status='completed' GROUP BY o.customer_id HAVING COUNT(DISTINCT t.root_id)=(SELECT COUNT(*) FROM categories WHERE parent_category_id IS NULL) ORDER BY o.customer_id")
    add("test", "hard", "ratio", "For each carrier with delivered shipments, return carrier, delivered_shipment_count, late_shipment_count and late_delivery_rate. Exclude undelivered shipments from both numerator and denominator. Order by carrier.", ["carrier", "delivered_shipment_count", "late_shipment_count", "late_delivery_rate"],
        "SELECT carrier,COUNT(*),SUM(CASE WHEN delivered_at>promised_at THEN 1 ELSE 0 END),1.0*SUM(CASE WHEN delivered_at>promised_at THEN 1 ELSE 0 END)/COUNT(*) FROM shipments WHERE delivered_at IS NOT NULL GROUP BY carrier ORDER BY carrier")
    add("test", "hard", "calendar", "Return all 12 months of 2025 as month (YYYY-MM), successful_payment_count and collected_cents, including zero-collection months. Assign payments by paid_at, and count succeeded payments only. Order by month.", ["month", "successful_payment_count", "collected_cents"],
        "WITH RECURSIVE months(d) AS (SELECT '2025-01-01' UNION ALL SELECT date(d,'+1 month') FROM months WHERE d<'2025-12-01') SELECT substr(m.d,1,7),COUNT(p.payment_id),COALESCE(SUM(p.amount_cents),0) FROM months m LEFT JOIN payments p ON p.status='succeeded' AND p.paid_at>=m.d AND p.paid_at<date(m.d,'+1 month') GROUP BY m.d ORDER BY m.d")
    add("test", "hard", "window", "Return category_id and average_top_two_current_prices_cents for every directly assigned category containing at least two products. Choose its two most expensive products, including inactive ones, breaking equal prices by product_id. Order by category_id.", ["category_id", "average_top_two_current_prices_cents"],
        "WITH ranked AS (SELECT category_id,current_price_cents,ROW_NUMBER() OVER(PARTITION BY category_id ORDER BY current_price_cents DESC,product_id) AS rn FROM products) SELECT category_id,AVG(current_price_cents) FROM ranked WHERE rn<=2 GROUP BY category_id HAVING COUNT(*)=2 ORDER BY category_id")
    add("test", "hard", "conditional_aggregation", "Return every customer_id, completed_order_count, cancelled_order_count and gross_revenue_cents from completed orders. Include customers with no orders and do not multiply order counts by their line items. Order by customer_id.", ["customer_id", "completed_order_count", "cancelled_order_count", "gross_revenue_cents"],
        "WITH i AS (SELECT order_id,SUM(quantity*unit_price_cents-discount_cents) AS gross FROM order_items GROUP BY order_id) SELECT c.customer_id,SUM(CASE WHEN o.status='completed' THEN 1 ELSE 0 END),SUM(CASE WHEN o.status='cancelled' THEN 1 ELSE 0 END),COALESCE(SUM(CASE WHEN o.status='completed' THEN i.gross ELSE 0 END),0) FROM customers c LEFT JOIN orders o ON o.customer_id=c.customer_id LEFT JOIN i ON i.order_id=o.order_id GROUP BY c.customer_id ORDER BY c.customer_id")
    add("test", "hard", "correlated_subquery", "Return product_id, supplier_id and supply_cost_cents for the cheapest supplier of every product having suppliers. Break cost ties by supplier_id. Order by product_id.", ["product_id", "supplier_id", "supply_cost_cents"],
        "WITH ranked AS (SELECT product_id,supplier_id,supply_cost_cents,ROW_NUMBER() OVER(PARTITION BY product_id ORDER BY supply_cost_cents,supplier_id) AS rn FROM product_suppliers) SELECT product_id,supplier_id,supply_cost_cents FROM ranked WHERE rn=1 ORDER BY product_id")
    add("test", "hard", "cohort", "For each month containing a customer's first completed order in 2025, return cohort_month (YYYY-MM), customer_count and returning_next_month_count. A returning customer has a completed order in the calendar month immediately after their first completed order month. Count each customer once. Order by cohort_month.", ["cohort_month", "customer_count", "returning_next_month_count"],
        "WITH firsts AS (SELECT customer_id,date(MIN(ordered_at),'start of month') AS month FROM orders WHERE status='completed' GROUP BY customer_id) SELECT substr(f.month,1,7),COUNT(*),SUM(CASE WHEN EXISTS(SELECT 1 FROM orders o WHERE o.customer_id=f.customer_id AND o.status='completed' AND o.ordered_at>=date(f.month,'+1 month') AND o.ordered_at<date(f.month,'+2 months')) THEN 1 ELSE 0 END) FROM firsts f WHERE f.month>='2025-01-01' AND f.month<'2026-01-01' GROUP BY f.month ORDER BY f.month")
    return items


def main() -> None:
    path = DATA / "items.jsonl"
    if path.exists():
        raise SystemExit("items.jsonl already exists; edit and review it directly rather than overwriting labels.")
    items = catalog()
    assert sum(item["split"] == "dev" for item in items) == 10
    assert sum(item["split"] == "test" for item in items) == 50
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")
    print(f"Wrote {len(items)} draft items to {path}")


if __name__ == "__main__":
    main()
