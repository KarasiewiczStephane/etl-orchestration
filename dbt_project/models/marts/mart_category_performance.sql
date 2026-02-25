with transactions as (
    select * from {{ ref('int_customer_transactions') }}
)

select
    category,
    count(*) as transaction_count,
    sum(amount) as total_amount,
    avg(amount) as avg_amount,
    min(amount) as min_amount,
    max(amount) as max_amount,
    count(distinct customer_id) as unique_customers
from transactions
group by category
order by total_amount desc
