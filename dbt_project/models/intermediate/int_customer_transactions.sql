with transactions as (
    select * from {{ ref('stg_transactions') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
)

select
    t.transaction_id,
    t.customer_id,
    c.name as customer_name,
    c.tier as customer_tier,
    t.amount,
    t.category,
    t.transaction_date
from transactions t
left join customers c on t.customer_id = c.customer_id
