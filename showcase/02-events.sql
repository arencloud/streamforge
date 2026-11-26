-- Use only synthetic records in the dedicated showcase database.
\set ON_ERROR_STOP on
INSERT INTO public.orders(id, customer_name, amount, status)
VALUES (910001, 'Showcase One', 12.50, 'created'),
       (910002, 'Showcase Two', 25.00, 'created');
UPDATE public.orders SET status='paid', updated_at=now() WHERE id=910001;
DELETE FROM public.orders WHERE id=910002;
