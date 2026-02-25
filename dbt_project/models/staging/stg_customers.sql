with source as (
    select * from {{ source('raw', 'customers') }}
)

select
    customer_id,
    name,
    email,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    tier,
    _loaded_at
from source
