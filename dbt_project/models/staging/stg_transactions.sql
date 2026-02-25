with source as (
    select * from {{ source('raw', 'transactions') }}
)

select
    transaction_id,
    customer_id,
    amount,
    cast(transaction_date as timestamp) as transaction_date,
    category,
    _loaded_at
from source
