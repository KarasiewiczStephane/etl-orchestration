with customer_orders as (
    select * from {{ ref('int_customer_orders') }}
),

customer_transactions as (
    select * from {{ ref('int_customer_transactions') }}
)

select
    co.customer_id,
    co.customer_name,
    co.customer_email,
    co.customer_tier,
    count(distinct co.order_id) as total_orders,
    sum(co.line_total) as total_order_revenue,
    avg(co.line_total) as avg_order_value,
    min(co.order_date) as first_order_date,
    max(co.order_date) as last_order_date,
    count(distinct ct.transaction_id) as total_transactions,
    coalesce(sum(ct.amount), 0) as total_transaction_amount
from customer_orders co
left join customer_transactions ct on co.customer_id = ct.customer_id
group by
    co.customer_id,
    co.customer_name,
    co.customer_email,
    co.customer_tier
