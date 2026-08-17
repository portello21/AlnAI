create or replace function public.rog_vector_dimensions(input_embedding extensions.vector)
returns integer
language sql
immutable
security invoker
set search_path = ''
as 'select extensions.vector_dims(input_embedding)';
