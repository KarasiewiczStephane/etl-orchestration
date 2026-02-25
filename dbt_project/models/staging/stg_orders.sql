with source as (
    select * from {{ source('raw', 'orders') }}
)

select
    order_id,
    customer_id,
    product_id,
    quantity,
    price,
    cast(order_date as timestamp) as order_date,
    status,
    _loaded_at
from source
