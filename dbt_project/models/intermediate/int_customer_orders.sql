with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
)

select
    o.order_id,
    o.customer_id,
    c.name as customer_name,
    c.email as customer_email,
    c.tier as customer_tier,
    o.product_id,
    o.quantity,
    o.price,
    o.quantity * o.price as line_total,
    o.order_date,
    o.status
from orders o
left join customers c on o.customer_id = c.customer_id
