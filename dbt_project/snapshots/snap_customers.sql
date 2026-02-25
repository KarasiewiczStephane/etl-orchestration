{% snapshot snap_customers %}

{{
    config(
        target_schema='snapshots',
        unique_key='customer_id',
        strategy='timestamp',
        updated_at='updated_at',
        invalidate_hard_deletes=True
    )
}}

select
    customer_id,
    name,
    email,
    tier,
    created_at,
    updated_at
from {{ source('raw', 'customers') }}

{% endsnapshot %}
