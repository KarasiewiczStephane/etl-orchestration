{% snapshot snap_orders %}

{{
    config(
        target_schema='snapshots',
        unique_key='order_id',
        strategy='timestamp',
        updated_at='order_date',
        invalidate_hard_deletes=True
    )
}}

select
    order_id,
    customer_id,
    product_id,
    quantity,
    price,
    order_date,
    status
from {{ source('raw', 'orders') }}

{% endsnapshot %}
