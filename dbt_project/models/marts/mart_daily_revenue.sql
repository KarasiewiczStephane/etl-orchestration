with orders as (
    select * from {{ ref('int_customer_orders') }}
)

select
    cast(order_date as date) as order_day,
    count(distinct order_id) as order_count,
    sum(line_total) as total_revenue,
    avg(line_total) as avg_order_value,
    count(distinct customer_id) as unique_customers
from orders
group by cast(order_date as date)
order by order_day
